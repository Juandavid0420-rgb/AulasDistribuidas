# Andres Manosalva
import zmq
import json
import time
from random import randint

def programa_aca(nombre_programa, semestre, salones, laboratorios, ip_facultad, puerto_facultad):
    """
    Proceso que representa un programa académico. Envía solicitudes de aulas a la facultad y guarda las solicitudes.
    
    Args:
        nombre_programa (str): Nombre del programa (e.g., "Programa de Ingeniería de Sistemas").
        semestre (str): Semestre académico (e.g., "2025-10").
        salones (int): Número de salones solicitados (e.g., 5).
        laboratorios (int): Número de laboratorios solicitados (e.g., 2).
        ip_facultad (str): IP de la máquina donde están las facultades (e.g., "192.168.1.102").
        puerto_facultad (int): Puerto donde la facultad escucha (e.g., 3391).
    """
    # Crear contexto ZeroMQ para manejar sockets
    context = zmq.Context()
    # Configurar socket REQ para comunicarse con la facultad (request-reply síncrono)
    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://{ip_facultad}:{puerto_facultad}")

    print(f"Programa {nombre_programa} iniciado para el semestre {semestre}...")

    while True:
        # Crear solicitud de aulas en formato JSON
        solicitud = {
            "programa": nombre_programa,
            "semestre": semestre,
            "salones": salones,
            "laboratorios": laboratorios
        }

        # Enviar solicitud a la facultad
        socket.send_json(solicitud)
        print(f"Programa {nombre_programa} envió solicitud: {solicitud}")

        # Recibir confirmación de la facultad
        respuesta = socket.recv_json()
        print(f"Programa {nombre_programa} recibió confirmación: {respuesta}")

        # Guardar la solicitud enviada en un archivo para persistencia
        with open(f"solicitudes_{nombre_programa}_{semestre}.txt", "a") as f:
            f.write(f"{json.dumps(solicitud)}\n")

        # Esperar 10 segundos antes de enviar la próxima solicitud
        time.sleep(10)

if __name__ == "__main__":
    # Punto de entrada del programa
    import sys
    if len(sys.argv) != 6:
        print("Uso: python programa_academico.py <nombre_programa> <semestre> <salones> <laboratorios> <ip_facultad>")
        sys.exit(1)
    # IP de la máquina donde están las facultades (PC2)
    ip_facultad = sys.argv[5]
    # Puerto donde las facultades escuchan (fijo en 3391)
    puerto_facultad = 3391
    # Iniciar el programa académico con los parámetros proporcionados
    programa_aca(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), ip_facultad, puerto_facultad)