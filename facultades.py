# Andres Manosalva
import zmq
import threading
import json
import time
import os

def manejar_programas(socket_programas, solicitudes_programas, tiempos_inicio):
    """
    Maneja las solicitudes de los programas académicos de forma síncrona usando el patrón request-reply.
    
    Args:
        socket_programas (zmq.Socket): Socket REP para comunicarse con los programas académicos.
        solicitudes_programas (list): Lista para almacenar las solicitudes recibidas de los programas.
        tiempos_inicio (list): Lista para almacenar los tiempos de inicio de las solicitudes.
    """
    while True:
        # Recibir solicitud de un programa académico en formato JSON
        mensaje = socket_programas.recv_json()
        # Registrar el tiempo de inicio para medir el tiempo total de procesamiento
        tiempo_inicio = time.time()
        print(f"Facultad recibió solicitud de programa: {mensaje}")
        # Almacenar la solicitud y el tiempo de inicio
        solicitudes_programas.append(mensaje)
        tiempos_inicio.append(tiempo_inicio)
        # Enviar confirmación al programa académico
        socket_programas.send_json({"status": "Solicitud recibida"})

def facultad(nombre_facultad, semestre, ip_servidor, puerto_inicial):
    """
    Proceso principal de la facultad. Gestiona la comunicación con programas académicos y el servidor central.
    
    Args:
        nombre_facultad (str): Nombre de la facultad (e.g., "Facultad de Ingeniería").
        semestre (str): Semestre académico (e.g., "2025-10").
        ip_servidor (str): IP del servidor central o réplica (e.g., "192.168.1.103").
        puerto_inicial (int): Puerto inicial del servidor central (e.g., 3389).
    """
    # Crear contexto ZeroMQ para manejar sockets
    context = zmq.Context()

    # Configurar socket REP para comunicarse con los programas académicos (request-reply síncrono)
    socket_programas = context.socket(zmq.REP)
    socket_programas.bind("tcp://*:3391")  # Escucha en el puerto 3391 para programas académicos

    # Configurar socket DEALER para comunicarse con el servidor central (request-reply asíncrono)
    socket_servidor = context.socket(zmq.DEALER)
    socket_servidor.setsockopt_string(zmq.IDENTITY, nombre_facultad)  # Identidad única para la facultad

    # Determinar el puerto activo inicial del servidor (central o réplica)
    puerto_activo = puerto_inicial
    if os.path.exists("puerto_activo.txt"):
        with open("puerto_activo.txt", "r") as f:
            puerto_activo = int(f.read().strip())
    # Conectar al servidor (central o réplica) usando la IP y puerto activo
    socket_servidor.connect(f"tcp://{ip_servidor}:{puerto_activo}")

    # Listas para almacenar solicitudes y tiempos de inicio de los programas académicos
    solicitudes_programas = []
    tiempos_inicio = []

    # Iniciar hilo para manejar solicitudes de programas académicos de forma concurrente
    thread_programas = threading.Thread(target=manejar_programas, args=(socket_programas, solicitudes_programas, tiempos_inicio))
    thread_programas.daemon = True  # Hilo demonio para que termine al cerrar el programa
    thread_programas.start()

    print(f"Facultad {nombre_facultad} iniciada para el semestre {semestre}...")

    while True:
        # Consolidar solicitudes cada 5 segundos
        time.sleep(5)
        if solicitudes_programas:
            # Calcular el total de salones y laboratorios solicitados por todos los programas
            total_salones = sum(prog["salones"] for prog in solicitudes_programas)
            total_laboratorios = sum(prog["laboratorios"] for prog in solicitudes_programas)
            # Crear solicitud consolidada para enviar al servidor central
            solicitud = {
                "semestre": semestre,
                "facultad": nombre_facultad,
                "programa": solicitudes_programas[0]["programa"],  # Usar el programa de la primera solicitud
                "salones": total_salones,
                "laboratorios": total_laboratorios
            }

            # Verificar si el puerto activo cambió (para tolerancia a fallas)
            if os.path.exists("puerto_activo.txt"):
                with open("puerto_activo.txt", "r") as f:
                    nuevo_puerto = int(f.read().strip())
                    if nuevo_puerto != puerto_activo:
                        # Desconectar del puerto anterior y conectar al nuevo puerto
                        socket_servidor.disconnect(f"tcp://{ip_servidor}:{puerto_activo}")
                        puerto_activo = nuevo_puerto
                        socket_servidor.connect(f"tcp://{ip_servidor}:{puerto_activo}")
                        print(f"Facultad {nombre_facultad} cambió al puerto {puerto_activo}")

            # Enviar solicitud consolidada al servidor central
            socket_servidor.send_json(solicitud)
            print(f"Facultad {nombre_facultad} envió solicitud: {solicitud}")

            # Recibir respuesta del servidor central en formato JSON
            respuesta = socket_servidor.recv_json()
            print(f"Facultad {nombre_facultad} recibió respuesta: {respuesta}")

            # Registrar el tiempo total de procesamiento (desde la solicitud hasta la respuesta)
            tiempo_fin = time.time()
            for tiempo_inicio in tiempos_inicio:
                with open(f"metricas_{nombre_facultad}_{semestre}.txt", "a") as f:
                    f.write(f"Tiempo total: {tiempo_fin - tiempo_inicio}\n")

            # Guardar la asignación recibida en un archivo para persistencia
            with open(f"asignaciones_{nombre_facultad}_{semestre}.txt", "a") as f:
                f.write(f"{json.dumps(respuesta)}\n")

            # Limpiar listas para el próximo ciclo
            solicitudes_programas.clear()
            tiempos_inicio.clear()

if __name__ == "__main__":
    # Punto de entrada del programa
    import sys
    if len(sys.argv) != 3:
        print("Uso: python facultades.py <nombre_facultad> <semestre>")
        sys.exit(1)
    # IP del servidor central (PC3) o réplica (PC1), dependiendo del puerto activo
    ip_servidor = "192.168.1.103"  # IP de PC3 (servidor central)
    # Iniciar la facultad con los parámetros proporcionados
    facultad(sys.argv[1], sys.argv[2], ip_servidor, 3389)  # Puerto inicial 3389 (servidor central)