# llm_admin.py

import os
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Variável global para armazenar o modelo de IA inicializado
__model = None

def configure_llm(api_key: str):
    """
    Configura o modelo de IA Generativa com a chave de API fornecida.

    Args:
        api_key (str): A chave de API do Google AI.

    Returns:
        bool: True se a configuração for bem-sucedida, False caso contrário.
    """
    global __model
    if not api_key:
        __model = None
        return False
    try:
        genai.configure(api_key=api_key)
        __model = genai.GenerativeModel('gemini-1.5-flash')
        return True
    except Exception as e:
        st.error(f"❌ Erro ao configurar a API do Google: {e}")
        __model = None
        return False

def get_model():
    """Retorna a instância do modelo de IA inicializado."""
    return __model

def extract_players_from_file_llm(file_content: str):
    """
    Usa o LLM para extrair dados de jogadores a partir do conteúdo de um arquivo.

    Args:
        file_content (str): O conteúdo do arquivo em formato de string.

    Returns:
        pd.DataFrame: Um DataFrame do Pandas com os dados dos jogadores ou None em caso de falha.
    """
    model = get_model()
    if not model:
        st.error("❌ Modelo de IA não inicializado. Verifique se a API Key está configurada.")
        return None

    table_structure = """
    - Nome (VARCHAR(200), obrigatório)
    - Data_Nascimento (DATE, formato 'AAAA-MM-DD')
    - Posicao (VARCHAR(100))
    - Nacionalidade (VARCHAR(100))
    - Numero_Partidas (INTEGER)
    - Total_Minutos_Jogados (INTEGER)
    - Gols_Marcados (INTEGER)
    - Assistencias (INTEGER)
    - Pe_Dominante (VARCHAR(1), 'D' para Destro ou 'E' para Esquerdo)
    """

    prompt = f"""
    Você é um assistente especialista em extrair dados de jogadores de futebol a partir de documentos.
    Analise o conteúdo do documento a seguir e extraia uma lista de jogadores.
    O único campo obrigatório é o 'Nome'. Para os outros campos, se a informação não estiver presente, deixe o valor nulo (null).

    A estrutura de dados para cada jogador deve seguir o seguinte modelo:
    {table_structure}

    Conteúdo do documento:
    ---
    {file_content}
    ---

    Sua resposta DEVE ser uma lista de objetos JSON, onde cada objeto representa um jogador.
    Exemplo de Resposta:
    ```json
    [
      {{
        "Nome": "Ronaldo Nazário",
        "Data_Nascimento": "1976-09-22",
        "Posicao": "Atacante",
        "Nacionalidade": "Brasileiro",
        "Pe_Dominante": "D"
      }}
    ]
    ```
    Se nenhum jogador for encontrado, retorne uma lista vazia [].
    """
    try:
        response = model.generate_content(prompt)
        json_str = response.text.split('```json')[1].split('```')[0].strip()
        data = json.loads(json_str)
        return pd.DataFrame(data)
    except (IndexError, json.JSONDecodeError):
        st.error("❌ A IA retornou um formato inesperado. Não foi possível decodificar o JSON.")
        if 'response' in locals() and hasattr(response, 'text'):
            st.info(f"Resposta recebida da IA:\n{response.text}")
        return None
    except Exception as e:
        st.error(f"❌ Ocorreu um erro ao processar os dados com a IA: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            st.info(f"Resposta da IA:\n{response.text}")
        return None