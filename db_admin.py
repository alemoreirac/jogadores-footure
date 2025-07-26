# db_admin.py (Versão Melhorada com Rastreabilidade e Correções)
import psycopg2
import streamlit as st
import os
from dotenv import load_dotenv
from models import Clube, Elenco, Jogador
from typing import List, Optional, Tuple, Any

load_dotenv()

# Credenciais do PostgreSQL
DB_HOST = os.getenv("DB_HOST", "")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        print("[DB_ADMIN] Conexão com o banco de dados estabelecida com sucesso.")
        return conn
    except Exception as e:
        print(f"[DB_ADMIN] ERRO: Falha na conexão com o banco de dados: {e}")
        st.error(f"Falha na conexão com o banco de dados: {e}")
        return None

def execute_query(query: str, params: Optional[tuple] = None, fetch: Optional[str] = None) -> Any:
    """
    Executa uma query no banco de dados de forma segura com rastreabilidade.
    - Para operações de escrita (INSERT, UPDATE, DELETE), retorna True em caso de sucesso e False em caso de falha.
    - Para operações de leitura (SELECT), retorna os dados ou None em caso de falha.
    """
    print("--- [DB_ADMIN] EXECUTANDO QUERY ---")
    print(f"  [QUERY]: {query.strip()}")
    print(f"  [PARAMS]: {params}")
    print(f"  [FETCH]: {fetch}")

    conn = get_db_connection()
    if conn is None:
        print("[DB_ADMIN] ERRO: Conexão com o BD não disponível.")
        return False if not fetch else None

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch == "one":
                    result = cur.fetchone()
                    print(f"  [DB_RESULT] fetchone retornado.")
                    return result
                elif fetch == "all":
                    result = cur.fetchall()
                    print(f"  [DB_RESULT] fetchall retornado com {len(result) if result else 0} linhas.")
                    return result
                
                # Para operações de escrita (INSERT, UPDATE, DELETE), o commit é implícito pelo 'with conn:'.
                # Retorna True para indicar sucesso.
                print(f"  [DB_RESULT] Operação de escrita bem-sucedida. Linhas afetadas: {cur.rowcount}")
                return True
    except psycopg2.Error as e:
        print(f"[DB_ADMIN] ERRO DE BANCO DE DADOS: {e}")
        st.error(f"Erro no Banco de Dados: {e}")
        return False if not fetch else None
    except Exception as e:
        print(f"[DB_ADMIN] ERRO GERAL AO EXECUTAR QUERY: {e}")
        st.error(f"Erro ao executar query: {e}")
        return False if not fetch else None
    finally:
        if conn:
            conn.close()
            print("[DB_ADMIN] Conexão com o BD fechada.")
            print("------------------------------------")


# --- Funções CRUD para Clubes ---
def create_clube(clube: Clube) -> bool:
    """Cria um novo clube no banco de dados."""
    query = "INSERT INTO Clube (Nome, Ano, Cidade) VALUES (%s, %s, %s)"
    params = (clube.nome, clube.ano, clube.cidade)
    return execute_query(query, params)

def read_clubes() -> List[Clube]:
    """Lê todos os clubes do banco de dados."""
    query = "SELECT ID, Nome, Ano, Cidade FROM Clube ORDER BY Nome"
    rows = execute_query(query, fetch="all")
    clubes = []
    if rows:
        for row in rows:
            clube = Clube(id=row[0], nome=row[1], ano=row[2], cidade=row[3])
            clubes.append(clube)
    return clubes

def update_clube(clube: Clube) -> bool:
    """Atualiza um clube existente no banco de dados."""
    if clube.id is None:
        return False
    query = "UPDATE Clube SET Nome = %s, Ano = %s, Cidade = %s WHERE ID = %s"
    params = (clube.nome, clube.ano, clube.cidade, clube.id)
    return execute_query(query, params)

def delete_clube(clube_id: int) -> bool:
    """Exclui um clube do banco de dados."""
    query = "DELETE FROM Clube WHERE ID = %s"
    params = (clube_id,)
    return execute_query(query, params)

# --- Funções CRUD para Elencos ---
def create_elenco(elenco: Elenco) -> bool:
    """Cria um novo elenco no banco de dados."""
    query = "INSERT INTO Elenco (FK_clube, Ano, Descricao) VALUES (%s, %s, %s)"
    params = (elenco.fk_clube, elenco.ano, elenco.descricao)
    return execute_query(query, params)

def read_elencos_por_clube(clube_id: int) -> List[Elenco]:
    """Lê todos os elencos de um clube específico."""
    query = "SELECT ID, FK_clube, Ano, Descricao FROM Elenco WHERE FK_clube = %s ORDER BY Ano DESC, Descricao"
    params = (clube_id,)
    rows = execute_query(query, params, fetch="all")
    elencos = []
    if rows:
        for row in rows:
            elenco = Elenco(id=row[0], fk_clube=row[1], ano=row[2], descricao=row[3])
            elencos.append(elenco)
    return elencos

def update_elenco(elenco: Elenco) -> bool:
    """Atualiza um elenco existente no banco de dados."""
    if elenco.id is None:
        return False
    query = "UPDATE Elenco SET FK_clube = %s, Ano = %s, Descricao = %s WHERE ID = %s"
    params = (elenco.fk_clube, elenco.ano, elenco.descricao, elenco.id)
    return execute_query(query, params)

def delete_elenco(elenco_id: int) -> bool:
    """Exclui um elenco do banco de dados."""
    query = "DELETE FROM Elenco WHERE ID = %s"
    params = (elenco_id,)
    return execute_query(query, params)

# --- Funções CRUD para Jogadores ---
def create_jogador(jogador: Jogador) -> bool:
    """Cria um novo jogador no banco de dados."""
    query = """
    INSERT INTO Jogadores (Elenco_ID, Nome, Data_Nascimento, Posicao, Nacionalidade, Pe_Dominante, Numero_Partidas, Total_Minutos_Jogados, Gols_Marcados, Assistencias)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        jogador.elenco_id, jogador.nome, jogador.data_nascimento, jogador.posicao,
        jogador.nacionalidade, jogador.pe_dominante, jogador.numero_partidas,
        jogador.total_minutos_jogados, jogador.gols_marcados, jogador.assistencias
    )
    return execute_query(query, params)

def read_jogadores() -> List[Tuple[Any, ...]]:
    """Lê todos os jogadores com informações de clube e elenco."""
    query = """
    SELECT J.ID, J.Nome, J.Data_Nascimento, J.Posicao, C.Nome as Clube, E.Descricao as Elenco
    FROM Jogadores J
    JOIN Elenco E ON J.Elenco_ID = E.ID
    JOIN Clube C ON E.FK_clube = C.ID
    ORDER BY C.Nome, J.Nome
    """
    return execute_query(query, fetch="all") or []

def get_jogador(id: int) -> Optional[tuple]:
    """Busca um jogador completo pelo ID e retorna como uma tupla."""
    query = "SELECT ID, Elenco_ID, Nome, Data_Nascimento, Posicao, Nacionalidade, Pe_Dominante, Numero_Partidas, Total_Minutos_Jogados, Gols_Marcados, Assistencias FROM Jogadores WHERE ID = %s"
    params = (id,)
    # CORREÇÃO: Adicionado fetch="one" para garantir que a consulta retorne um único resultado.
    return execute_query(query, params, fetch="one")
                               
def update_jogador(jogador: Jogador) -> bool:
    """Atualiza um jogador existente no banco de dados."""
    if jogador.id is None:
        return False
    query = """
    UPDATE Jogadores
    SET Elenco_ID = %s, Nome = %s, Data_Nascimento = %s, Posicao = %s,
        Nacionalidade = %s, Pe_Dominante = %s, Numero_Partidas = %s,
        Total_Minutos_Jogados = %s, Gols_Marcados = %s, Assistencias = %s
    WHERE ID = %s
    """
    params = (
        jogador.elenco_id, jogador.nome, jogador.data_nascimento, jogador.posicao,
        jogador.nacionalidade, jogador.pe_dominante, jogador.numero_partidas,
        jogador.total_minutos_jogados, jogador.gols_marcados, jogador.assistencias,
        jogador.id
    )
    return execute_query(query, params)

def delete_jogador(jogador_id: int) -> bool:
    """Exclui um jogador do banco de dados."""
    query = "DELETE FROM Jogadores WHERE ID = %s"
    params = (jogador_id,)
    return execute_query(query, params)