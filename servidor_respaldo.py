import zmq
import threading
import json
import time
from random import randint

# Clase para gestionar los recursos disponibles (salones y laboratorios)
class Recursos:
    def __init__(self):
        """Inicializa los recursos disponibles y un candado para sincronización."""
        self.salones_disponibles = 380  # Total de salones disponibles según el proyecto
        self.laboratorios_disponibles = 60  # Total de laboratorios disponibles según el proyecto
        self.lock = threading.Lock()  # Candado para evitar conflictos en asignaciones concurrentes

    def asignar_aulas(self, salones_solicitados, laboratorios_solicitados, facultad, programa):
        """
        Asigna salones y laboratorios según la disponibilidad. Si no hay suficientes laboratorios,
        adapta salones como aulas móviles.
        
        Args:
            salones_solicitados (int): Número de salones solicitados.
            laboratorios_solicitados (int): Número de laboratorios solicitados.
            facultad (str): Nombre de la facultad que hace la solicitud.
            programa (str): Nombre del programa académico asociado a la solicitud.
        
        Returns:
            dict: Diccionario con la asignación (salones, laboratorios, aulas móviles, y alerta si aplica).
        """
        with self.lock:  # Sincronizar acceso a recursos para evitar conflictos entre hilos
            # Inicializar diccionario para almacenar la asignación
            asignacion = {"salones": 0, "laboratorios": 0, "aulas_moviles": 0, "alerta": ""}
            
            # Asignar salones según disponibilidad
            salones_asignados = min(salones_solicitados, self.salones_disponibles)
            self.salones_disponibles -= salones_asignados
            asignacion["salones"] = salones_asignados

            # Asignar laboratorios según disponibilidad
            laboratorios_asignados = min(laboratorios_solicitados, self.laboratorios_disponibles)
            self.laboratorios_disponibles -= laboratorios_asignados
            asignacion["laboratorios"] = laboratorios_asignados

            # Si faltan laboratorios, usar salones como aulas móviles
            laboratorios_faltantes = laboratorios_solicitados - laboratorios_asignados
            if laboratorios_faltantes > 0:
                aulas_moviles = min(laboratorios_faltantes, self.salones_disponibles)
                self.salones_disponibles -= aulas_moviles
                asignacion["aulas_moviles"] = aulas_moviles

            # Generar alerta si no se puede cumplir la solicitud completamente
            if (salones_solicitados > salones_asignados or 
                laboratorios_solicitados > (laboratorios_asignados + aulas_moviles)):
                asignacion["alerta"] = "No hay suficientes aulas para cumplir la solicitud."

            # Guardar la asignación en un archivo para persistencia
            with open("asignaciones_respaldo.txt", "a") as f:
                f.write(f"Facultad: {facultad}, Programa: {programa}, Asignación: {json.dumps(asignacion)}\n")

            return asignacion

# Clase para registrar métricas de rendimiento
class Metricas:
    def __init__(self):
        """Inicializa las métricas de rendimiento y un candado para sincronización."""
        self.tiempos_respuesta = []  # Lista de tiempos de respuesta del servidor a las facultades
        self.tiempos_totales = []  # Lista de tiempos totales desde solicitud hasta respuesta
        self.atendidos = 0  # Contador de solicitudes atendidas satisfactoriamente
        self.no_atendidos = 0  # Contador de solicitudes no atendidas por falta de recursos
        self.lock = threading.Lock()  # Candado para sincronizar acceso a métricas

    def registrar_respuesta(self, tiempo_inicio, tiempo_fin, asignacion):
        """
        Registra el tiempo de respuesta y si la solicitud fue atendida o no.
        
        Args:
            tiempo_inicio (float): Tiempo de inicio de la solicitud.
            tiempo_fin (float): Tiempo de finalización de la solicitud.
            asignacion (dict): Diccionario con la asignación y posible alerta.
        """
        with self.lock:  # Sincronizar acceso a métricas
            # Calcular tiempo de respuesta
            tiempo = tiempo_fin - tiempo_inicio
            self.tiempos_respuesta.append(tiempo)
            # Incrementar contadores según si hubo alerta o no
            if asignacion["alerta"]:
                self.no_atendidos += 1
            else:
                self.atendidos += 1
            # Guardar métrica en un archivo
            with open("metricas_respaldo.txt", "a") as f:
                f.write(f"Tiempo respuesta: {tiempo}, Atendido: {not asignacion['alerta']}\n")

    def registrar_tiempo_total(self, tiempo):
        """
        Registra el tiempo total desde que se hace la solicitud hasta que se atiende.
        
        Args:
            tiempo (float): Tiempo total de procesamiento.
        """
        with self.lock:
            self.tiempos_totales.append(tiempo)

    def generar_reporte(self):
        """
        Genera un reporte con las métricas solicitadas en la Tabla 3 del proyecto.
        
        Returns:
            dict: Diccionario con las métricas calculadas.
        """
        promedio_respuesta = sum(self.tiempos_respuesta) / len(self.tiempos_respuesta) if self.tiempos_respuesta else 0
        min_respuesta = min(self.tiempos_respuesta) if self.tiempos_respuesta else 0
        max_respuesta = max(self.tiempos_respuesta) if self.tiempos_respuesta else 0
        promedio_total = sum(self.tiempos_totales) / len(self.tiempos_totales) if self.tiempos_totales else 0
        return {
            "promedio_respuesta": promedio_respuesta,
            "min_respuesta": min_respuesta,
            "max_respuesta": max_respuesta,
            "promedio_total": promedio_total,
            "atendidos": self.atendidos,
            "no_atendidos": self.no_atendidos
        }

def manejar_solicitud(socket, recursos, metricas):
    """
    Procesa solicitudes de las facultades de forma concurrente usando hilos.
    
    Args:
        socket (zmq.Socket): Socket ROUTER para recibir y enviar mensajes.
        recursos (Recursos): Instancia de la clase Recursos para gestionar salones y laboratorios.
        metricas (Metricas): Instancia de la clase Metricas para registrar métricas.
    """
    while True:
        # Recibir mensaje de una facultad (multipart: identidad + mensaje)
        [identity, mensaje] = socket.recv_multipart()
        # Registrar tiempo de inicio para medir tiempo de respuesta
        tiempo_inicio = time.time()
        # Decodificar mensaje JSON recibido
        solicitud = json.loads(mensaje.decode('utf-8'))
        print(f"Servidor réplica recibió solicitud: {solicitud}")

        # Procesar solicitud y asignar aulas
        asignacion = recursos.asignar_aulas(
            solicitud["salones"], solicitud["laboratorios"], solicitud["facultad"], solicitud["programa"]
        )

        # Registrar tiempo de respuesta
        tiempo_fin = time.time()
        metricas.registrar_respuesta(tiempo_inicio, tiempo_fin, asignacion)

        # Enviar respuesta a la facultad en formato JSON (multipart: identidad + respuesta)
        respuesta = json.dumps(asignacion).encode('utf-8')
        socket.send_multipart([identity, respuesta])
        print(f"Servidor réplica respondió: {asignacion}")

def servidor_respaldo(puerto):
    """
    Inicia el servidor réplica, configura el socket y lanza hilos para manejar solicitudes.
    
    Args:
        puerto (int): Puerto donde el servidor réplica escuchará (e.g., 3390).
    """
    # Crear contexto ZeroMQ para manejar sockets
    context = zmq.Context()
    # Configurar socket ROUTER para comunicación asíncrona con las facultades
    socket = context.socket(zmq.ROUTER)
    socket.bind(f"tcp://*:{puerto}")  # Vincularse al puerto especificado

    # Crear instancias de Recursos y Metricas
    recursos = Recursos()
    metricas = Metricas()

    # Crear 5 hilos para manejar solicitudes concurrentemente
    num_hilos = 5
    for _ in range(num_hilos):
        thread = threading.Thread(target=manejar_solicitud, args=(socket, recursos, metricas))
        thread.daemon = True  # Hilo demonio para que termine al cerrar el programa
        thread.start()

    print(f"Servidor réplica iniciado en puerto {puerto}...")
    # Mantener el servidor activo
    while True:
        time.sleep(1)

if __name__ == "__main__":
    # Punto de entrada del programa
    import sys
    if len(sys.argv) != 2:
        print("Uso: python servidor_respaldo.py <puerto>")
        sys.exit(1)
    # Iniciar el servidor réplica con el puerto proporcionado
    servidor_respaldo(int(sys.argv[1]))