FROM python:3.14-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências de sistema para compilação (necessário para pglast/psycopg)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do projeto
COPY . .

# Expõe a porta que o Uvicorn vai usar
EXPOSE 8000

# Comando para subir a API
CMD ["uvicorn", "main_api:app", "--host", "0.0.0.0", "--port", "8000"]