# Usamos una imagen base oficial de Python
FROM python:3.11-slim

# Variables de entorno para que Python no cree archivos .pyc y muestre logs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Creamos el directorio de la app
WORKDIR /app

# Copiamos requirements primero (para que Docker cachee la instalación)
COPY requirements.txt /app/

# Instalamos dependencias del sistema necesarias para psycopg2
RUN apt-get update \
    && apt-get install -y gcc libpq-dev python3-dev \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiamos todo el código de la app
COPY . /app/

# Exponemos el puerto que usa Flask
EXPOSE 8080

# Comando para correr la app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "application:app"]
