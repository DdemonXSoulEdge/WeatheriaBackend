#!/bin/bash
# Script para iniciar todos los microservicios del proyecto
# Activa el entorno virtual y ejecuta cada servicio en segundo plano

# Definimos el directorio del proyecto
PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"

# Creamos el directorio de logs si no existe
mkdir -p "$LOG_DIR"

# Verificamos si el entorno virtual existe
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: No se encontró el entorno virtual en $VENV_DIR"
    exit 1
fi

# Activamos el entorno virtual
source "$VENV_DIR/bin/activate"

# Verificamos si los puertos están ocupados
check_port() {
    local port=$1
    if lsof -i:$port > /dev/null; then
        echo "Error: El puerto $port ya está en uso."
        exit 1
    fi
}


check_port 5001


# Función para iniciar un servicio
start_service() {
    local service_dir=$1
    local service_name=$2
    local port=$3
    echo "Iniciando $service_name en el puerto $port..."
    cd "$PROJECT_DIR/$service_dir" || exit 1
    python3 app.py > "$LOG_DIR/$service_name.log" 2>&1 &
    echo "$!" > "$LOG_DIR/$service_name.pid" # Guardamos el PID del proceso
    cd "$PROJECT_DIR"
}

# Iniciamos cada microservicio
start_service "api_gateway" "api_gateway" 5001


echo "Todos los microservicios han sido iniciados."
echo "Logs disponibles en $LOG_DIR"
echo "Para detener los servicios, usa el comando 'stop_services.sh'."