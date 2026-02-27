# Usando Python 3.12-slim para imagem menor
FROM python:3.12-slim

# Instalar postgresql-client para pg_dump/pg_restore rodarem direto no container
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar o arquivo de dependências
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todos os arquivos da pasta app para dentro do container
COPY app/ /app

# Comando padrão para rodar o scraper (caso não queira rodar outro script por padrão)
CMD ["python", "scraper_indicadores.py"]
