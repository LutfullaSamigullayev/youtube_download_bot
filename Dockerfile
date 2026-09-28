FROM python:3.11-slim

# FFmpeg va boshqa kerakli paketlarni o'rnatish
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Talablarni nusxalash va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Manba kodini nusxalash
COPY . .

# Botni ishga tushirish
CMD ["python", "main.py"]
