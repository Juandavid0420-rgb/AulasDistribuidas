import zmq
import time
import os

def health_check(ip_servidor, puerto_principal, puerto_respaldo):
    """
    Monitorea el servidor central y cambia al servidor réplica si falla, actualizando el puerto activo.
    
    Args:
        ip_servidor (str): IP del servidor central o réplica (e.g., "192.168.1.103" o "192.168.1.101").
        puerto_principal (int): Puerto del servidor central (e.g., 3389).
        puerto_respaldo (int): Puerto del servidor réplica (e.g., 3390).
    """
    # Crear contexto ZeroMQ para manejar sockets
    context = zmq.Context()
    # Configurar socket REQ para enviar pings al servidor
    socket = context.socket(zmq.REQ)

    # Establecer puerto activo inicial (servidor central)
    puerto_activo = puerto_principal
    with open("puerto_activo.txt", "w") as f:
        f.write(str(puerto_activo))

    while True:
        try:
            # Conectar al servidor activo (central o réplica)
            socket.connect(f"tcp://{ip_servidor}:{puerto_activo}")
            # Enviar mensaje de ping
            socket.send_string("ping")
            # Esperar respuesta con un timeout de 1 segundo
            socket.recv_string(timeout=1000)
            # Desconectar para el próximo ciclo
            socket.disconnect(f"tcp://{ip_servidor}:{puerto_activo}")
            print(f"Servidor en puerto {puerto_activo} está activo.")
        except zmq.error.Again:
            # Si no hay respuesta, el servidor ha fallado
            print(f"Servidor en puerto {puerto_activo} no responde.")
            # Cambiar al otro puerto (central -> réplica o réplica -> central)
            puerto_activo = puerto_respaldo if puerto_activo == puerto_principal else puerto_principal
            # Actualizar el archivo puerto_activo.txt para que las facultades se reconecten
            with open("puerto_activo.txt", "w") as f:
                f.write(str(puerto_activo))
            print(f"Cambiando al servidor en puerto {puerto_activo}...")
        # Esperar 2 segundos antes de la próxima verificación
        time.sleep(2)

if __name__ == "__main__":
    # Punto de entrada del programa
    import sys
    if len(sys.argv) != 3:
        print("Uso: python health_check.py <puerto_principal> <puerto_respaldo>")
        sys.exit(1)
    # Determinar la IP según el puerto (central en 3389, réplica en 3390)
    ip_servidor = "192.168.1.103" if int(sys.argv[1]) == 3389 else "192.168.1.101"
    # Iniciar el health-check con los puertos proporcionados
    health_check(ip_servidor, int(sys.argv[1]), int(sys.argv[2]))