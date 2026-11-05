Meta-Ride | Pull Aceros
Proyecto académico de Modelado y Simulación de Sistemas. Prototipo web para visualizar solicitudes internas de rollos de acero hacia las estampadoras ENN1–ENN6 y experimentar con la disponibilidad de operadores y montacargas mediante simulación de eventos discretos.
Estado: prototipo de demostración. Las pantallas operativas usan datos de ejemplo; el módulo de simulación ejecuta cálculos en Python con SimPy usando supuestos académicos. No es un sistema productivo ni está conectado a inventario real.

Tecnologías
- Frontend: React (JavaScript/JSX), Vite, Tailwind CSS, componentes UI y Lucide React.
- Backend: Python, FastAPI y Uvicorn.
- Simulación: SimPy.
- Control de versiones: Git y GitHub.
Funcionalidades del prototipo
- Inicio de sesión de demostración y vistas por rol.
- Resumen operativo y panel Kanban de solicitudes.
- Formulario de nueva solicitud, inventario, cambio de turno, historial y administración (interfaces demostrativas).
- Simulador de surtimiento con cantidad de solicitudes, montacargas, operadores y tipo de demanda.
- Indicadores de tiempo promedio de espera y entrega, entregas completadas durante el turno y porcentaje de cumplimiento.
- Comparación de escenarios de 1 a 4 montacargas.
Requisitos previos
Instalar:
1. Node.js con npm (versión compatible con la versión de Vite instalada en el proyecto).
2. Python 3.12 (recomendado; también puede funcionar con otras versiones compatibles).
3. Git (solo para clonar o subir el proyecto).
4. Un editor como Visual Studio Code.
Verificar en PowerShell:
node --version
npm --version
python --version
py -3.12 --version
git --version
Nota para Windows: si py --version intenta abrir una instalación inexistente de Python 3.13, utiliza explícitamente py -3.12 para crear el entorno virtual. No hace falta reinstalar Python si 3.12 funciona.
Estructura del proyecto
Proyecto Modelado/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── src/
│   ├── App.jsx
│   └── SimulationPage.jsx
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
└── README.md
La estructura puede incluir otros archivos de configuración y componentes de React.
Instalación desde cero
1. Descargar el repositorio
git clone https://github.com/TU-USUARIO/TU-REPOSITORIO.git
cd TU-REPOSITORIO
Reemplaza la URL y el nombre de carpeta por los reales. Si ya tienes el proyecto abierto en VS Code, no necesitas clonarlo: abre la terminal en la carpeta que contiene package.json.
2. Instalar las dependencias de React
En una terminal ubicada en la raíz del proyecto:
npm install
Si el proyecto incluye package-lock.json actualizado, también puedes utilizar npm ci para una instalación reproducible.
3. Preparar el backend de Python
Abre otra terminal en VS Code, desde la raíz del proyecto:
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
No es necesario activar el entorno virtual, ya que los comandos llaman directamente a su intérprete.
4. Iniciar FastAPI + SimPy
Desde backend/:
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
El backend se ejecuta por defecto en:
- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
- Prueba de salud: http://127.0.0.1:8000/salud
En /docs puedes probar POST /simular con Try it out → Execute. Una respuesta HTTP 200 indica que la solicitud se procesó correctamente.

Mantén abierta esta terminal mientras uses el simulador.
5. Iniciar el frontend React
Abre una segunda terminal ubicada en la raíz del proyecto (no en backend/):
npm run dev
Abre la dirección mostrada por Vite, normalmente:
- http://localhost:5173/
Inicia sesión en la vista de demostración y selecciona Simulación en el menú lateral.
Uso del simulador
1. Indica el número de solicitudes de acero.
2. Ajusta el número de montacargas.
3. Ajusta el número de operadores.
4. Selecciona demanda normal o con urgencias.
5. Haz clic en Ejecutar simulación.
6. Revisa los indicadores y utiliza Comparar 1 a 4 montacargas para evaluar alternativas.
Supuestos del modelo académico
Parámetro	Valor predeterminado
Duración del turno	480 min (8 horas)
Tiempo de preparación	5–12 min
Tiempo de traslado	8–20 min
Réplicas	10
Semilla base	42
Solicitudes por defecto	50
Montacargas por defecto	2
Operadores por defecto	3


En la implementación actual, un operador y un montacargas se ocupan conjuntamente durante preparación y traslado. Las solicitudes pueden completarse después del fin del turno. Los valores son hipotéticos y deben validarse antes de usar resultados para decisiones reales.
Configuración opcional de la API
El frontend utiliza por defecto http://127.0.0.1:8000. Para cambiarlo, crea un archivo .env en la raíz del frontend con:
VITE_SIM_API=http://127.0.0.1:8000
Reinicia npm run dev después de modificar variables de entorno. No subas .env a GitHub; para compartir configuración, usa .env.example sin secretos.
Comandos rápidos para iniciar el proyecto en Windows
Terminal 1 — Backend (desde la raíz):
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
Terminal 2 — Frontend (desde la raíz):
npm run dev
Para detener cualquiera de los servidores, presiona Ctrl + C en su terminal.
Publicar cambios en GitHub
Desde la raíz del proyecto:
git status
git add .
git commit -m "Actualizar prototipo y simulador Meta-Ride"
git push
Para un repositorio local que todavía no está conectado a GitHub:
git init
git remote add origin https://github.com/TU-USUARIO/TU-REPOSITORIO.git
git branch -M main
Luego haz git add ., git commit y git push -u origin main. No fuerces el push si el repositorio remoto ya tiene archivos o commits; primero sincroniza las ramas.
Problemas comunes
py --version falla y menciona Python 3.13: ejecuta py -3.12 --version y utiliza py -3.12 -m venv .venv.

Identifier SimulationPage has already been declared: en src/App.jsx conserva import SimulationPage from "./SimulationPage"; y elimina la función provisional function SimulationPage() que esté duplicada dentro del mismo archivo.

No conecta la simulación / Failed to fetch: comprueba que el backend siga activo en el puerto 8000 y que http://127.0.0.1:8000/docs abra correctamente. Revisa VITE_SIM_API si cambiaste el puerto.

npm no encuentra package.json: verifica que la terminal esté en la carpeta raíz del frontend.

No se encuentra requirements.txt: ejecuta los comandos de Python desde la carpeta backend.

Vite usa el puerto 5174: es normal si 5173 está ocupado; abre la URL exacta que muestra la terminal.
Limitaciones y trabajo futuro
- Conectar solicitudes e inventario a una base de datos persistente.
- Sustituir la autenticación demostrativa por usuarios reales.
- Calibrar llegadas, tiempos y recursos con datos observados en la operación.
- Integrar estadísticas históricas y exportación de resultados.
Meta-Ride — Proyecto académico de Modelado y Simulación de Sistemas.