````markdown
# Proyecto Sistemas Distribuidos: Distribución de Aulas con Tolerancia a Fallos

Este repositorio contiene los scripts Python necesarios para desplegar un sistema de distribución de aulas en tres máquinas virtuales (VM) con tolerancia a fallos. Cada componente y su interacción están descritos a continuación. El flujo general es:

1. **Programas Académicos** envían solicitudes de asignación de aulas a las Facultades.  
2. **Facultades** agrupan las solicitudes, leen `puerto_activo.txt` para decidir si conectarse al **Servidor Central** o al **Servidor Réplica**.  
3. **Servidor Central** atiende la petición y **replica** la misma solicitud al **Servidor Réplica** antes de responder.  
4. Si el **Servidor Central** cae, la Facultad, al cambiar manualmente `puerto_activo.txt`, enviará al **Servidor Réplica**, que ya estará sincronizado.

---

## Índice

1. [Estructura del Proyecto](#estructura-del-proyecto)  
2. [Requisitos Previos](#requisitos-previos)  
3. [Parcheo Mínimo en Servidores (Central y Réplica)](#parcheo-m%C3%ADnimo-en-servidores-central-y-r%C3%A9plica)  
4. [Configuración de `puerto_activo.txt`](#configuraci%C3%B3n-de-puerto_activotxt)  
5. [Despliegue por Máquina](#despliegue-por-m%C3%A1quina)  
   - [VM 1: Servidor Central (10.43.103.179)](#vm-1-servidor-central-1043103179)  
   - [VM 2: Servidor Réplica (10.43.96.70)](#vm-2-servidor-r%C3%A9plica-10439670)  
   - [VM 3: Facultades + Health-check (10.43.96.67)](#vm-3-facultades--health-check-10439667)  
6. [Ejemplo de Flujo Completo](#ejemplo-de-flujo-completo)  
7. [Simulación de Fallo y Conmutación Manual](#simulaci%C3%B3n-de-fallo-y-conmutaci%C3%B3n-manual)  
8. [Archivos de Salida / Registros](#archivos-de-salida--registros)  
9. [Notas Adicionales](#notas-adicionales)  

---

## 1. Estructura del Proyecto

```text
proyecto_distribuidos/
├── servidor_central.py     # Lógica del Servidor Central + réplica a Servidor Réplica
├── servidor_respaldo.py    # Lógica del Servidor Réplica (recibe replicaciones)
├── facultades.py           # Lógica de cada Facultad (bind 3391, reenvía a servidor activo)
├── programa_aca.py         # Programa Académico (envía solicitudes cada 10s a Facultad)
├── health_check.py         # (Opcional) script para inicializar puerto_activo.txt
└── puerto_activo.txt       # Archivo que indica “3389” (Central) o “3390” (Réplica)
````

* **servidor\_central.py**:

  * Recibe solicitudes JSON de Facultades en un socket ROUTER (puerto 3389).
  * Cada petición se repica antes al Servidor Réplica (puerto 3390).
  * Atiende localmente, asigna aulas, registra métricas y envía respuesta back.
  * Se ejecuta con un único hilo para evitar “segmentation fault”.

* **servidor\_respaldo.py**:

  * Escucha en un socket ROUTER (puerto 3390) las solicitudes replicadas del Central.
  * Procesa cada JSON (asignación de aulas) y envía un ACK (“pong”) al Central.
  * Registra métricas y loguea en pantalla la misma información que el Central.
  * También usa un solo hilo.

* **facultades.py**:

  * Cada Facultad hace `bind("tcp://*:3391")` para recibir peticiones de programas académicos.
  * Lee `puerto_activo.txt` para saber a qué servidor conectarse (`tcp://IP:<puerto>`).
  * Agrupa todas las peticiones recibidas en <5s y envía un JSON combinado al servidor activo.
  * Registra métricas y asignaciones en archivos locales.

* **programa\_aca.py**:

  * Se conecta a la Facultad en `tcp://<IP_FACULTAD>:3391`.
  * Cada 10 segundos envía un JSON con `{ programa, semestre, salones, laboratorios }`.
  * Espera `recv_json()` y guarda la respuesta en un archivo local.

* **health\_check.py** (opcional):

  * Hace ping a Central (10.43.103.179:3389) y, si responde, escribe “3389” en `puerto_activo.txt`.
  * Si no responde, hace ping a Réplica (10.43.96.70:3390) y, si responde, escribe “3390”.
  * Luego sale. Sirve solo para inicializar `puerto_activo.txt`.

* **puerto\_activo.txt**:

  * Contiene un único número: `3389` (Central) o `3390` (Réplica).
  * Cada Facultad lo lee cada vez que va a reenviar una solicitud.

---

## 2. Requisitos Previos

En **cada** VM (Central, Réplica y Facultad) debes:

1. Tener instalado Python 3.10 (o superior) y PyZMQ.
2. Abrir el puerto correspondiente en el firewall `ufw`.
3. Clonar/copiar los archivos `.py` al directorio `/home/estudiante/proyecto_distribuidos/`.
4. Dar permisos de lectura/escritura a todos los `.py`.

Comandos genéricos:

```bash
sudo apt update
sudo apt install -y python3 python3-pip ufw
pip3 install pyzmq

# Crear carpeta de proyecto
mkdir -p /home/estudiante/proyecto_distribuidos
cd /home/estudiante/proyecto_distribuidos

# Copiar aquí los archivos .py
chmod 644 *.py

# Habilitar y abrir puertos en ufw (según VM)
sudo ufw enable
sudo ufw allow <puerto>  # 3389 en Central, 3390 en Réplica, 3391 en Facultad
sudo ufw reload
```

---

## 3. Parcheo Mínimo en Servidores (Central y Réplica)

Antes de ejecutar, hay que modificar ligeramente `servidor_central.py` y `servidor_respaldo.py` para:

1. **Corregir unpack de `recv_multipart()`** (usar `frames[0]` y `frames[-1]`).
2. **Reducir a un solo hilo** (eliminar el bucle de 5 hilos).

A continuación tienes los códigos completos ya parcheados. Reemplaza los contenidos originales con estos.

---

### 3.1. `servidor_central.py`

```python
import zmq
import threading
import json
import time

# IP y puerto donde escucha el Réplica
IP_REPLICA    = "10.43.96.70"
PUERTO_REPLICA = 3390

# --- CLASES DE NEGOCIO ---

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
                return {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": salones_solicitados,
                    "laboratorios_asignados": laboratorios_solicitados,
                    "estado": "asignado"
                }
            else:
                return {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": 0,
                    "laboratorios_asignados": 0,
                    "estado": "rechazado"
                }

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
            if self.tiempos_totales:
                promedio = sum(self.tiempos_totales) / len(self.tiempos_totales)
                minimo   = min(self.tiempos_totales)
                maximo   = max(self.tiempos_totales)
            else:
                promedio = minimo = maximo = 0
            return {
                "promedio_respuesta": promedio,
                "min_respuesta": minimo,
                "max_respuesta": maximo,
                "atendidos": self.atendidos,
                "no_atendidos": self.no_atendidos
            }

# --- FUNCIÓN QUE ATIENDE SOLICITUDES EN UN HILO ---

def manejar_solicitud(socket_router, recursos, metricas, zmq_context):
    while True:
        # Recibir multipart (puede haber frame vacío intermedio)
        frames   = socket_router.recv_multipart()
        identity = frames[0]
        payload  = frames[-1]          # JSON en bytes
        texto    = payload.decode("utf-8")

        # Parsear JSON
        try:
            solicitud = json.loads(texto)
        except json.JSONDecodeError:
            continue

        # REPLICAR a la Réplica
        try:
            rep_sock = zmq_context.socket(zmq.REQ)
            rep_sock.setsockopt(zmq.RCVTIMEO, 1000)  # timeout 1s
            rep_sock.connect(f"tcp://{IP_REPLICA}:{PUERTO_REPLICA}")
            rep_sock.send_string(texto)
            rep_sock.recv_string()  # espera "pong"
            rep_sock.close()
        except Exception:
            print(f"⚠️  No se pudo replicar al Réplica {IP_REPLICA}:{PUERTO_REPLICA}")

        # Procesar localmente
        tiempo_inicio = time.time()
        asignacion = recursos.asignar_aulas(
            solicitud["salones"],
            solicitud["laboratorios"],
            solicitud["facultad"],
            solicitud["programa"]
        )
        tiempo_fin = time.time()
        metricas.registrar_respuesta(tiempo_inicio, tiempo_fin, asignacion)

        # Enviar respuesta a la Facultad
        respuesta_bytes = json.dumps(asignacion).encode("utf-8")
        socket_router.send_multipart([identity, respuesta_bytes])

        print(f"Servidor Central - Recibió: {solicitud}")
        print(f"Servidor Central - Respondió: {asignacion}")

# --- FUNCIÓN PRINCIPAL ---

def servidor_central(puerto):
    context       = zmq.Context()
    socket_router = context.socket(zmq.ROUTER)
    socket_router.bind(f"tcp://*:{puerto}")

    recursos = Recursos()
    metricas = Metricas()

    # Arranca un solo hilo para manejar solicitudes
    hilo = threading.Thread(
        target=manejar_solicitud,
        args=(socket_router, recursos, metricas, context)
    )
    hilo.daemon = True
    hilo.start()

    print(f"Servidor Central iniciado en puerto {puerto}. Esperando solicitudes…")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python3 servidor_central.py <puerto>")
        sys.exit(1)
    puerto = int(sys.argv[1])
    servidor_central(puerto)
```

---

### 3.2. `servidor_respaldo.py`

```python
import zmq
import threading
import json
import time

# --- CLASES DE NEGOCIO (idénticas a las del Central) ---

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
                return {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": salones_solicitados,
                    "laboratorios_asignados": laboratorios_solicitados,
                    "estado": "asignado"
                }
            else:
                return {
                    "facultad": facultad,
                    "programa": programa,
                    "salones_asignados": 0,
                    "laboratorios_asignados": 0,
                    "estado": "rechazado"
                }

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
            if self.tiempos_totales:
                promedio = sum(self.tiempos_totales) / len(self.tiempos_totales)
                minimo   = min(self.tiempos_totales)
                maximo   = max(self.tiempos_totales)
            else:
                promedio = minimo = maximo = 0
            return {
                "promedio_respuesta": promedio,
                "min_respuesta": minimo,
                "max_respuesta": maximo,
                "atendidos": self.atendidos,
                "no_atendidos": self.no_atendidos
            }

# --- FUNCIÓN QUE ATIENDE REPLICACIONES EN UN HILO ---

def manejar_solicitud(socket_router, recursos, metricas):
    while True:
        # Recibir multipart
        frames   = socket_router.recv_multipart()
        identity = frames[0]
        payload  = frames[-1]
        texto    = payload.decode("utf-8")

        # Parsear JSON
        try:
            solicitud = json.loads(texto)
        except json.JSONDecodeError:
            continue

        # Procesar en réplica
        tiempo_inicio = time.time()
        asignacion = recursos.asignar_aulas(
            solicitud["salones"],
            solicitud["laboratorios"],
            solicitud["facultad"],
            solicitud["programa"]
        )
        tiempo_fin = time.time()
        metricas.registrar_respuesta(tiempo_inicio, tiempo_fin, asignacion)

        # Enviar ACK ("pong") al Central
        socket_router.send_multipart([identity, b"pong"])

        print(f"Servidor Réplica - Recibió replicación: {solicitud}")
        print(f"Servidor Réplica - Procesó asignación: {asignacion}")

# --- FUNCIÓN PRINCIPAL ---

def servidor_respaldo(puerto):
    context       = zmq.Context()
    socket_router = context.socket(zmq.ROUTER)
    socket_router.bind(f"tcp://*:{puerto}")

    recursos = Recursos()
    metricas = Metricas()

    # Un solo hilo para atender replicaciones
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
```

---

## 4. Configuración de `puerto_activo.txt`

En la **VM 3 (Facultades)** debes crear (o sobrescribir) este archivo para que diga inicialmente `3389` (Servidor Central). Más adelante, cuando simules la caída del Central, cambiarás a `3390` (Servidor Réplica):

```bash
# En VM 3 (10.43.96.67)
cd /home/estudiante/proyecto_distribuidos
echo "3389" > puerto_activo.txt
chmod 644 puerto_activo.txt
```

* Cuando quieras que la Facultad apunte al Réplica, ejecuta:

  ```bash
  echo "3390" > puerto_activo.txt
  ```

---

## 5. Despliegue por Máquina

A continuación, paso a paso, cómo ejecutar cada componente en su VM correspondiente.

### VM 1: Servidor Central (IP: 10.43.103.179)

```bash
# 1) Conectar a la máquina
ssh usuario@10.43.103.179

# 2) Ir al directorio del proyecto
cd /home/estudiante/proyecto_distribuidos

# 3) Instalar dependencias (si no lo has hecho ya)
sudo apt update
sudo apt install -y python3 python3-pip ufw
pip3 install pyzmq

# 4) Abrir el puerto 3389 en el firewall
sudo ufw allow 3389
sudo ufw reload

# 5) Verificar que servidor_central.py esté parcheado (un solo hilo + unpack seguro)

# 6) Opcional: sincronizar copia local de puerto_activo.txt
echo "3389" > puerto_activo.txt
chmod 644 puerto_activo.txt

# 7) Arrancar el Servidor Central en el puerto 3389
python3 servidor_central.py 3389
```

**Salida esperada**:

```
Servidor Central iniciado en puerto 3389. Esperando solicitudes…
```

### VM 2: Servidor Réplica (IP: 10.43.96.70)

```bash
# 1) Conectar a la máquina
ssh usuario@10.43.96.70

# 2) Ir al directorio del proyecto
cd /home/estudiante/proyecto_distribuidos

# 3) Instalar dependencias (si no lo has hecho)
sudo apt update
sudo apt install -y python3 python3-pip ufw
pip3 install pyzmq

# 4) Abrir el puerto 3390 en el firewall
sudo ufw allow 3390
sudo ufw reload

# 5) Verificar que servidor_respaldo.py esté parcheado (un solo hilo + unpack seguro)

# 6) Arrancar el Servidor Réplica en el puerto 3390
python3 servidor_respaldo.py 3390
```

**Salida esperada**:

```
Servidor Réplica iniciado en puerto 3390. Esperando replicaciones…
```

### VM 3: Facultades + Health-check (IP: 10.43.96.67)

```bash
# 1) Conectar a la máquina
ssh usuario@10.43.96.67

# 2) Ir al directorio del proyecto
cd /home/estudiante/proyecto_distribuidos

# 3) Instalar dependencias
sudo apt update
sudo apt install -y python3 python3-pip ufw
pip3 install pyzmq

# 4) Abrir el puerto 3391 en el firewall
sudo ufw allow 3391
sudo ufw reload

# 5) Crear y fijar puerto_activo.txt a "3389"
echo "3389" > puerto_activo.txt
chmod 644 puerto_activo.txt

# 6) Editar facultades.py para apuntar a la IP del Central
nano facultades.py
# Cambia: ip_servidor = "192.168.1.103"
# Por:      ip_servidor = "10.43.103.179"
# Guarda y cierra

# 7) Arrancar una o varias Facultades (cada una en segundo plano)
python3 facultades.py "Facultad de Ingeniería"       2025-10 &
python3 facultades.py "Facultad de Ciencias Sociales" 2025-10 &
# (puedes crear hasta 10 facultades simultáneas)

# 8) (Opcional) Ejecutar health_check.py una sola vez para validar
python3 health_check.py 10.43.103.179 3389 10.43.96.70 3390
# Debería imprimir que Central responde y grabar "3389" en puerto_activo.txt
```

**Salida esperada** (por cada Facultad):

```
Facultad <Nombre> iniciada para el semestre 2025-10...
```

---

## 6. Ejemplo de Flujo Completo

1. **Programa Académico envía solicitud** (puede correr en VM 1 o en cualquier otra máquina con acceso a la Facultad):

   ```bash
   # En VM 1 (o en otra máquina), dentro de /home/estudiante/proyecto_distribuidos
   python3 programa_aca.py "Programa de Prueba" 2025-10 7 3 10.43.96.67 &
   ```

   * **Salida (en su consola)**:

     ```
     Programa Programa de Prueba iniciado para el semestre 2025-10...
     Programa Programa de Prueba envió solicitud: {'programa': 'Programa de Prueba', 'semestre': '2025-10', 'salones': 7, 'laboratorios': 3}
     ```

2. **Facultad recibe y reenvía a Central** (VM 3, puerto 3391 → 10.43.103.179:3389):

   * Cada 5 s, la Facultad lee `puerto_activo.txt` (que contiene “3389”) y si hay solicitudes acumuladas, hace:

     ```
     Facultad Facultad de Ingeniería recibió solicitud de Programa de Prueba
     Facultad Facultad de Ingeniería envía a 10.43.103.179:3389 → {'programa': 'Programa de Prueba', 'semestre': '2025-10', 'salones': 7, 'laboratorios': 3}
     ```
   * Internamente:

     ```python
     socket_servidor.send_json(solicitud)       # a Central
     respuesta = socket_servidor.recv_json()
     ```

3. **Servidor Central procesa y replica** (VM 1, puerto 3389):

   * **Salida en consola**:

     ```
     Servidor Central - Recibió: {'salones': 7, 'laboratorios': 3, 'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba'}
     Servidor Central - Respondió: {'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba', 'salones_asignados': 7, 'laboratorios_asignados': 3, 'estado': 'asignado'}
     ```
   * Antes de procesar localmente, intenta replicar:

     ```
     rep_sock = context.socket(zmq.REQ)
     rep_sock.connect("tcp://10.43.96.70:3390")
     rep_sock.send_string(texto_JSON)
     rep_sock.recv_string()  # espera "pong"
     rep_sock.close()
     ```
   * Si la réplica está viva, devuelve “pong” en <1 s.

4. **Servidor Réplica recibe la replicación y confirma** (VM 2, puerto 3390):

   * **Salida en consola**:

     ```
     Servidor Réplica - Recibió replicación: {'salones': 7, 'laboratorios': 3, 'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba'}
     Servidor Réplica - Procesó asignación: {'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba', 'salones_asignados': 7, 'laboratorios_asignados': 3, 'estado': 'asignado'}
     ```
   * Luego envía `["identity", b"pong"]` de vuelta al Central.

5. **Facultad recibe la respuesta y la guarda** (VM 3):

   * La Facultad recibe:

     ```
     Facultad Facultad de Ingeniería recibió respuesta: {'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba', 'salones_asignados': 7, 'laboratorios_asignados': 3, 'estado': 'asignado'}
     ```
   * Guarda en `asignaciones_Facultad de Ingeniería_2025-10.txt` y `metricas_Facultad de Ingeniería_2025-10.txt`.

6. **Programa Académico recibe la respuesta y la guarda** (VM 1 u otra):

   * En la consola del Programa Académico:

     ```
     Programa Programa de Prueba recibió respuesta: {'facultad': 'Facultad de Ingeniería', 'programa': 'Programa de Prueba', 'salones_asignados': 7, 'laboratorios_asignados': 3, 'estado': 'asignado'}
     ```
   * Guarda en `solicitudes_Programa de Prueba_2025-10.txt`.

---

## 7. Simulación de Fallo y Conmutación Manual

Cuando desees simular que el **Servidor Central** falla y la Facultad debe comunicarse con el **Servidor Réplica**, sigue estos pasos:

1. **Detener el Central** (VM 1):

   ```bash
   # En la consola donde corre servidor_central.py (VM 1)
   Ctrl + C
   ```

   * Sale el mensaje de interrupción y el Central deja de escuchar en 3389.

2. **Cambiar manualmente `puerto_activo.txt` a “3390”** (VM 3):

   ```bash
   ssh usuario@10.43.96.67
   cd /home/estudiante/proyecto_distribuidos
   echo "3390" > puerto_activo.txt
   chmod 644 puerto_activo.txt
   ```

   * En las Facultades, verás en su siguiente iteración (en <5 s):

     ```
     Facultad Facultad de Ingeniería cambió al puerto 3390
     ```

3. **Verificar que el Réplica esté vivo (VM 2)**. Si no lo estaba, arráncalo:

   ```bash
   ssh usuario@10.43.96.70
   cd /home/estudiante/proyecto_distribuidos
   python3 servidor_respaldo.py 3390
   ```

4. **Nuevas solicitudes irán a la Réplica**

   * Cualquier Programa Académico que siga ejecutándose enviará su JSON a la Facultad; ésta, al leer “3390”, se reconectará:

     ```python
     socket_servidor.disconnect("tcp://10.43.103.179:3389")
     socket_servidor.connect("tcp://10.43.96.70:3390")
     ```
   * En VM 2 (Réplica) verás:

     ```
     Servidor Réplica - Recibió replicación: { ... }
     Servidor Réplica - Procesó asignación: { ... }
     ```
   * La Facultad imprimirá:

     ```
     Facultad Facultad de Ingeniería envía a 10.43.96.70:3390 → { ... }
     ```
   * Y el Programa Académico recibirá la respuesta normalmente.

5. **Recuperar el Central (opcional)**

   * Para volver a usar el Central, arranca de nuevo en VM 1:

     ```bash
     ssh usuario@10.43.103.179
     cd /home/estudiante/proyecto_distribuidos
     python3 servidor_central.py 3389
     ```
   * En VM 3 (Facultades), edita otra vez:

     ```bash
     echo "3389" > puerto_activo.txt
     ```
   * La Facultad detectará el cambio y se reconectará al Central.

---

## 8. Archivos de Salida / Registros

* **Facultades (VM 3)**:

  * `asignaciones_<Facultad>_<Semestre>.txt` → Cada línea es un JSON con la asignación recibida.
  * `metricas_<Facultad>_<Semestre>.txt` → Cada línea: `Tiempo total: X.XXXX` (tiempo en segundos de ida y vuelta).

* **Programa Académico (VM 1 u otra)**:

  * `solicitudes_<Programa>_<Semestre>.txt` → Cada línea: JSON de la respuesta recibida.

* **Consolas**:

  * VM 1: Logs de “Servidor Central – Recibió…” y “… Respondió…”.
  * VM 2: Logs de “Servidor Réplica – Recibió replicación…” y “… Procesó asignación…”.
  * VM 3: Logs de cada Facultad (recepción, reenvío, cambio de puerto).
  * El Programa Académico imprime petición enviada y respuesta recibida.

---

## 9. Notas Adicionales

* **Concurrencia**: ambos servidores usan un solo hilo para atender cada solicitud de forma secuencial. Esto evita errores de ZeroMQ por compartir sockets entre hilos.

* **Health-check (opcional)**: el script `health_check.py` solo se usa para inicializar `puerto_activo.txt` si no quieres editarlo manualmente. Por ejemplo:

  ```bash
  python3 health_check.py 10.43.103.179 3389 10.43.96.70 3390
  ```

  – Escribe “3389” o “3390” en `puerto_activo.txt` y luego sale. Desde ese momento, la Facultad usa ese valor.

* **IPs y Puertos**:

  * VM 1 (Central) → IP `10.43.103.179`, puerto **3389**
  * VM 2 (Réplica) → IP `10.43.96.70`, puerto **3390**
  * VM 3 (Facultades) → IP `10.43.96.67`, puerto **3391** (solo local para `bind`).

* **Permisos**: asegúrate de que todos los scripts `.py` y `puerto_activo.txt` tengan permisos de lectura/escritura según corresponda.

Con este **README.md** cuentas con toda la información para entender el funcionamiento y desplegar paso a paso el sistema en las tres máquinas, así como para probar el esquema de tolerancia a fallos (Central → Réplica). ¡Éxitos en tu despliegue!
