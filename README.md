
# Meta-Ride | Pull Aceros

### Sistema de Gestión y Simulación de Solicitudes de Acero

Proyecto académico desarrollado para la materia de **Modelado y Simulación de Sistemas** de la **Universidad Autónoma de Nuevo León (UANL)**.

Meta-Ride es un prototipo web diseñado para gestionar y visualizar solicitudes internas de rollos de acero hacia las estampadoras **ENN1–ENN6**.

Además, incorpora un simulador de eventos discretos desarrollado en Python que permite evaluar cómo cambia el desempeño del proceso al modificar la cantidad de montacargas, operadores y solicitudes.

> **Nota:** Este sistema es un prototipo académico. Las interfaces operativas utilizan datos de demostración y los resultados de simulación se generan mediante supuestos hipotéticos.

---

## Tecnologías utilizadas

| Componente | Tecnología |
|---|---|
| Frontend | React + JavaScript (JSX) |
| Herramienta de desarrollo | Vite |
| Diseño | Tailwind CSS |
| Componentes visuales | Lucide React y componentes UI |
| Backend | Python 3.12 |
| API | FastAPI |
| Servidor | Uvicorn |
| Motor de simulación | SimPy |
| Control de versiones | Git y GitHub |

---

## Funcionalidades

### 1. Gestión de solicitudes

- Inicio de sesión demostrativo con diferentes roles.
- Panel principal con indicadores operativos.
- Visualización de solicitudes mediante tablero Kanban.
- Registro de nuevas solicitudes de acero.
- Consulta de inventario.
- Visualización de historial de movimientos.
- Pantallas de cambio de turno y administración.

### 2. Simulación de eventos discretos

El simulador permite modificar:

- Cantidad de solicitudes de acero.
- Número de montacargas disponibles.
- Número de operadores disponibles.
- Tipo de demanda.

El modelo simula la atención de solicitudes durante un turno de 8 horas.

**Supuestos del modelo:**

| Parámetro | Valor |
|---|---|
| Duración del turno | 480 minutos |
| Preparación de material | 5 a 12 minutos |
| Traslado del material | 8 a 20 minutos |
| Réplicas de simulación | 10 |
| Atención normal | Orden de llegada (FIFO) |

### 3. Indicadores de simulación

El sistema calcula:

- Tiempo promedio de entrega.
- Tiempo promedio de espera.
- Entregas completadas durante el turno.
- Porcentaje de cumplimiento del turno.

También permite comparar escenarios utilizando entre **1 y 4 montacargas**.

---

# Instalación del proyecto

## 1. Requisitos previos

Antes de ejecutar el sistema, instalar:

- Node.js y npm.
- Python 3.12.
- Git.
- Visual Studio Code (recomendado).

Verificar las instalaciones desde PowerShell:

```powershell
node --version
npm --version
py -3.12 --version
git --version
```

---

## 2. Clonar el repositorio

Abrir PowerShell o la terminal de Visual Studio Code.

Ejecutar:

```powershell
git clone https://github.com/fcobonilla0902/pull_aceros.git
```

Entrar a la carpeta del proyecto:

```powershell
cd pull_aceros
```

---

## 3. Instalar dependencias del frontend

Desde la carpeta principal:

```powershell
npm install
```

Este comando instalará las dependencias necesarias para ejecutar React y Vite.

---

## 4. Configurar el backend de Python

Abrir otra terminal y entrar a la carpeta del backend:

```powershell
cd backend
```

Crear un entorno virtual utilizando Python 3.12:

```powershell
py -3.12 -m venv .venv
```

Instalar las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si no existe `requirements.txt`, instalar las dependencias principales:

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" simpy
```

---

# Ejecución del sistema

Para utilizar el proyecto se necesitan **dos terminales abiertas al mismo tiempo**.

## Terminal 1: Iniciar el backend

Desde la carpeta `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

El servidor estará disponible en:

http://127.0.0.1:8000

Documentación interactiva de la API:

http://127.0.0.1:8000/docs

**Importante:** Mantener esta terminal abierta.

---

## Terminal 2: Iniciar el frontend

Desde la carpeta principal del proyecto:

```powershell
npm run dev
```

Vite mostrará una dirección local, normalmente:

http://localhost:5173

Abrir esa dirección en el navegador para utilizar Meta-Ride.

---

# Funcionamiento de la simulación

El sistema utiliza la siguiente arquitectura:

```text
                USUARIO
                   |
                   v
          INTERFAZ REACT
                   |
                   v
            API FASTAPI
                   |
                   v
          SIMULADOR SIMPY
                   |
                   v
       CÁLCULO DE RESULTADOS
                   |
                   v
           RESPUESTA JSON
                   |
                   v
        RESULTADOS EN REACT
```

### Proceso de simulación

1. El usuario configura la cantidad de solicitudes, montacargas y operadores.
2. React envía los parámetros a FastAPI.
3. FastAPI ejecuta el modelo de simulación desarrollado con SimPy.
4. SimPy representa la llegada de solicitudes y la disponibilidad de recursos.
5. Se calculan los tiempos de espera y entrega.
6. El backend devuelve los resultados a React.
7. La interfaz presenta los indicadores para analizar el escenario.

### Comparación de escenarios

El sistema permite comparar el comportamiento del proceso utilizando diferentes cantidades de montacargas.

Esto ayuda a identificar posibles cuellos de botella y analizar alternativas para mejorar el surtimiento de acero.

---

# Estructura del proyecto

```text
pull_aceros/
|
|-- backend/
|   |-- main.py
|   |-- requirements.txt
|
|-- src/
|   |-- App.jsx
|   |-- SimulationPage.jsx
|   |-- ...
|
|-- package.json
|-- package-lock.json
|-- vite.config.js
|-- .gitignore
|-- README.md
```

La estructura mostrada representa los archivos principales del sistema.

---

# Solución de problemas

### Error: npm no se reconoce

Verificar que Node.js esté instalado:

```powershell
node --version
```

Si no está instalado, descargarlo desde:

https://nodejs.org/

### Error: No module named 'simpy'

Instalar las dependencias del backend:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Error: Could not read package.json

Este error ocurre cuando se ejecuta npm desde una carpeta incorrecta.

Regresar a la carpeta principal del proyecto, donde se encuentra `package.json`, y ejecutar:

```powershell
npm install
npm run dev
```

### Error: Failed to fetch

Puede ocurrir cuando React no consigue conectarse al backend.

Verificar que FastAPI esté ejecutándose:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Comprobar que la API responda en:

http://127.0.0.1:8000/docs

---

# Consideraciones

- Proyecto desarrollado con fines académicos.
- El simulador utiliza tiempos y distribuciones hipotéticas.
- Los resultados pueden variar según los parámetros configurados.
- El sistema no está conectado a un inventario industrial real.
- Se requieren datos operativos reales para validar el modelo antes de utilizarlo en decisiones de producción.

---

## Información académica

**Proyecto:** Meta-Ride | Pull Aceros

**Materia:** Modelado y Simulación de Sistemas

**Institución:** Universidad Autónoma de Nuevo León (UANL)

**Facultad:** Facultad de Ingeniería Mecánica y Eléctrica (FIME)

**Tipo de proyecto:** Prototipo web con simulación de eventos discretos.
