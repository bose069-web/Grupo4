# Imagen base con Python ya instalado
FROM python:3.12-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias (primero, para aprovechar la caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY app.py chat.py ./

# Puerto en el que escucha la API
EXPOSE 8000

# Comando al arrancar el contenedor
CMD ["python", "app.py"]
