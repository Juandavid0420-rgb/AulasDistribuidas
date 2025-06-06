# servidor_central.py

import zmq
import threading
import json
import time

# Clase para gestionar recursos (380 salones, 60 laboratorios)
class Recursos:
    def __init__(self):
        self.salones_disponibles = 380
        self.laboratorios_disponibles = 60
        self.lock = threading.Lock()

    def asignar_aulas(self, salones_solicitados, laboratorios_solicitados, facultad, programa):
        with self.lock:
            if (salones_solicitados <= self.salones_disponibles and
                laboratorios_solicitados <= self.laboratorios_disponibles):
                self.salones_disponibles -= salones_solicitados
                self.laboratorios_disponibles -= laboratorios_solicitados
                asignacion = {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": salones_solicitados,
                    "laboratorios_asignados": laboratorios_solicitados,
                    "estado": "asignado"
                }
            else:
                asignacion = {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": 0,
                    "laboratorios_asignados": 0,
                    "estado": "rechazado"
                }
        return asignacion

# Clase para registrar métricas de tiempo
class Metricas:
    def __init__(self):
        self.tiempos_totales = []
        self.atendidos = 0
        self.no_atendidos = 0
        self.lock = threading.Lock()

    def registrar_respuesta(self, inicio, fin, asignacion):
        tiempo_total = fin - inicio
        with self.lock:
            self.tiempos_totales.append(tiempo_total)
            if asignacion["estado"] == "asignado":
                self.atendidos += 1
            else:
                self.no_atendidos += 1

    def obtener_metricas(self):
        with self.lock:
            tiempos = self.tiempos_totales
            if tiempos:
                promedio = sum(tiempos) / len(tiempos)
                minimo = min(tiempos)
                maximo = max(tiempos)
            else:
                promedio = minimo = maximo = 0
            return {
                "promedio_respuesta": promedio,
                "min_respuesta": minimo,
                "max_respuesta": maximo,
                "atendidos": self.atendidos,
                "no_atendidos": self.no_atendidos
            }

def manejar_solicitud(socket, recursos, metricas):
    """
    Procesa solicitudes de las facultades de forma secuencial en un solo hilo.
    """
    while True:
        # Recibir multipart: identidad + payload
        frames   = socket.recv_multipart()
        identity = frames[0]
        mensaje  = frames[-1]

        tiempo_inicio = time.time()
        solicitud = json.loads(mensaje.decode('utf-8'))
        print(f"Servidor recibió solicitud: {solicitud}")

        asignacion = recursos.asignar_aulas(
            solicitud["salones"],
            solicitud["laboratorios"],
            solicitud["facultad"],
            solicitud["programa"]
        )

        tiempo_fin = time.time()
        metricas.registrar_respuesta(tiempo_inicio, tiempo_fin, asignacion)

        respuesta = json.dumps(asignacion).encode('utf-8')
        socket.send_multipart([identity, respuesta])
        print(f"Servidor respondió: {asignacion}")

def servidor_central(puerto):
    """
    Inicia el servidor central en el puerto indicado, usando un único hilo.
    """
    context = zmq.Context()
    socket  = context.socket(zmq.ROUTER)
    socket.bind(f"tcp://*:{puerto}")

    recursos = Recursos()
    metricas = Metricas()

    # Un solo hilo para no compartir el socket ROUTER
    thread = threading.Thread(
        target=manejar_solicitud,
        args=(socket, recursos, metricas)
    )
    thread.daemon = True
    thread.start()

    print(f"Servidor central iniciado en puerto {puerto}.")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python3 servidor_central.py <puerto>")
        sys.exit(1)
    puerto = int(sys.argv[1])
    servidor_central(puerto)
