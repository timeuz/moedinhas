# Usar imagem leve do Python
FROM python:3.10-slim

# Definir diretório de trabalho
WORKDIR /app

# Copiar dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do projeto
COPY . .

# Expor a porta do Flask
EXPOSE 5000

# Comando de inicialização
CMD ["python", "app.py"]
