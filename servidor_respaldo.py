import zmq
import threading
import json
import time

# --- CLASES DE NEGOCIO (idénticas a Central) ---

class Recursos:
    def __init__(self):
        self.salones_disponibles    = 380
        self.laboratorios_disponibles = 60
        self.lock = threading.Lock()

    def asignar_aulas(self, salones_solicitados, laboratorios_solicitados, facultad, programa):
        with self.lock:
            if (salones_solicitados <= self.salones_disponibles and
                laboratorios_solicitados <= self.laboratorios_disponibles):
                self.salones_disponibles    -= salones_solicitados
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

class Metricas:
    def __init__(self):
        self.tiempos_totales = []
        self.atendidos       = 0
        self.no_atendidos    = 0
        self.lock            = threading.Lock()

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
                minimo   = min(tiempos)
                maximo   = max(tiempos)
            else:
                promedio = minimo = maximo = 0
            return {
                "promedio_respuesta": promedio,
                "min_respuesta": minimo,
                "max_respuesta": maximo,
                "atendidos": self.atendidos,
                "no_atendidos": self.no_atendidos
            }

# --- FUNCIÓN QUE ATIENDE LA REPLICACIÓN EN UN HILO ---

def manejar_solicitud(socket_router, recursos, metricas):
    """
    Bucle único en un solo hilo para procesar las solicitudes replicadas desde Central.
    Cada mensaje contiene [identity, ..., payload], donde payload es el JSON original.
    """
    while True:
        # 1) Recibir multipart
        frames   = socket_router.recv_multipart()
        identity = frames[0]
        payload  = frames[-1]
        texto    = payload.decode("utf-8")

        # 2) Parsear JSON
        try:
            solicitud = json.loads(texto)
        except json.JSONDecodeError:
            # Si llegara algo corrupto, lo ignoramos
            continue

        # 3) Procesar localmente en la Réplica
        tiempo_inicio = time.time()
        asignacion = recursos.asignar_aulas(
            solicitud["salones"],
            solicitud["laboratorios"],
            solicitud["facultad"],
            solicitud["programa"]
        )
        tiempo_fin = time.time()
        metricas.registrar_respuesta(tiempo_inicio, tiempo_fin, asignacion)

        # 4) Enviar un ACK (“pong”) de vuelta al Central
        socket_router.send_multipart([identity, b"pong"])

        # 5) Log en consola para que veas la misma info que en Central
        print(f"Servidor Réplica - Recibió replicación: {solicitud}")
        print(f"Servidor Réplica - Procesó asignación: {asignacion}")

def servidor_respaldo(puerto):
    """
    1) Crea un único zmq.Context()
    2) ROUTER bind en tcp://*:<puerto>
    3) Lanza UN solo hilo que ejecuta manejar_solicitud(...)
    """
    context      = zmq.Context()
    socket_router = context.socket(zmq.ROUTER)
    socket_router.bind(f"tcp://*:{puerto}")

    recursos = Recursos()
    metricas = Metricas()

    # UN solo hilo para evitar compartir sockets
    hilo = threading.Thread(
        target=manejar_solicitud,
        args=(socket_router, recursos, metricas)
    )
    hilo.daemon = True
    hilo.start()

    print(f"Servidor Réplica iniciado en puerto {puerto}. Esperando replicaciones…")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python3 servidor_respaldo.py <puerto>")
        sys.exit(1)
    puerto = int(sys.argv[1])
    servidor_respaldo(puerto)
