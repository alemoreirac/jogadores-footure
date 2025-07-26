# Usa uma imagem base oficial do Python
FROM python:3.11-slim-buster

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de requisitos para o diretório de trabalho
# É melhor copiar apenas o requirements.txt primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Streamlit usa por padrão (8501)
EXPOSE 8501

# Comando para rodar a aplicação Streamlit quando o contêiner iniciar
# 'streamlit run' executa o script principal da sua aplicação
# Certifique-se de que 'your_app.py' é o nome do seu arquivo principal do Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
