# 🔥 Gestión de Aulas - Sistemas Distribuidos  

📌 **Proyecto de Introducción a los Sistemas Distribuidos**  
📅 **Período Académico:** 2025-10  
🏫 **Universidad:** Pontificia Universidad Javeriana  

## 📖 Descripción  

Este proyecto implementa un **sistema distribuido en Ubuntu** para la gestión y asignación de aulas en una universidad. Se utiliza **comunicación con sockets en Python** para la comunicación entre procesos distribuidos y maneja concurrencia con **hilos**. El sistema permite la asignación eficiente de aulas y laboratorios, asegurando **tolerancia a fallos** y **persistencia de datos**.  

## 🚀 Características  

✅ Comunicación con **sockets TCP y UDP** en **Ubuntu**  
✅ Implementación de **procesos concurrentes** con `std::thread`  
✅ **Tolerancia a fallos** con servidor de respaldo y health-check  
✅ **Persistencia de datos** en archivos o base de datos  
✅ **Pruebas de rendimiento** con medición de tiempos de respuesta  

## 🏗️ Arquitectura  

- **Servidor Central (DTI):** Atiende solicitudes y gestiona la asignación de aulas.  
- **Facultades (10 procesos):** Reciben solicitudes de programas académicos y se comunican con el servidor.  
- **Programas Académicos (50 procesos):** Envían solicitudes de aulas a sus facultades.  
- **Health-check:** Detecta fallos y activa un servidor de respaldo.  

## 📂 Estructura del Proyecto  

```plaintext
📁 sistema-distribuido-aulas/
├── servidor.py         # Servidor central
├── facultad.py         # Cliente TCP (Facultad)
├── programa.py         # Cliente UDP o TCP (Programa académico)
 

```
## 🛠️ Instalación
**1️⃣ Instalar dependencias**
```plaintext
sudo apt update  
sudo apt install build-essential net-tools  
```
**2️⃣ Clonar el repositorio**
```plaintext
git clone (https://github.com/Juandavid0420-rgb/AulasDistribuidas.git) 
cd AulasDistribuidas  
```
**3️⃣ Compilar el proyecto**
```plaintext
make
```
**4️⃣ Ejecutar el servidor**
```plaintext
./servidor  
```
**5️⃣ Ejecutar las facultades**
```plaintext
./facultad  
```
**6️⃣ Ejecutar un programa académico**
```plaintext
./programa  
```
## 🧪 Pruebas
 
- **Unitarias**: Validación de solicitudes y respuestas.
- **Carga**: Pruebas con 500 solicitudes concurrentes.
- **Fallas**: Simulación de caída del servidor y activación del respaldo.

## 🖊️ Autores
👤 Juan David Sánchez
📧 **Contacto**: juandsanchez@javeriana.edu.co

### **📌 Instrucciones adicionales**

- **Asegúrate de ejecutar los comandos en una terminal de Ubuntu.**
- **Si `make` no está instalado, ejecuta:** 
```plaintext
  sudo apt install make
``` 
- **Para verificar los sockets abiertos:** `netstat -tulnp`  

Este `README.md` está completamente adaptado a **Ubuntu**. 🚀 

