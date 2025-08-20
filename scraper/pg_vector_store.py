import uuid
import json
import psycopg2
from typing import List, Dict, Any, Callable, Tuple
import logging
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import BaseModel, Field
import os

import dotenv
from dotenv import load_dotenv
import traceback
from google import genai
from google.genai import types

load_dotenv() 
#client = genai.Client()

API_KEY= os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)



# Configuração do logging para ter um nível de detalhe maior
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PostgresVectorStore")
EMBEDDING_TABLE = "aux.embeddings"

class PgVectorStore:
    def __init__(self):
        try:
            db_host = os.environ.get("DB_HOST", "localhost")
            db_port = os.environ.get("DB_PORT", "5432")
            db_user = os.environ.get("POSTGRES_USER", "postgres")
            db_password = os.environ.get("POSTGRES_PASSWORD", "secretpassword")
            db_name = os.environ.get("POSTGRES_DB", "rag_db")

            self.connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            self.table_name = EMBEDDING_TABLE
            #logger.info("PgVectorStore inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro na inicialização do PgVectorStore: {e}")
            raise

    def embed(self, text: str) -> List[float]:
        try:
            response = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            # O retorno é response.embeddings, não response.embedding
            if not response.embeddings or len(response.embeddings) == 0:
                logger.error("Nenhum embedding retornado pela API.")
                return []
            
            embedding = response.embeddings[0].values  # <- pega o primeiro embedding
            
            if len(embedding) != 768:
                logger.error(f"Dimensão incorreta do embedding: {len(embedding)}. Esperado: 768")
                return []
            
            #logger.info("Embedding gerado com sucesso.")
            return embedding
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            logger.error(traceback.format_exc())
            return []


    def _get_connection(self):
        try:
            conn = psycopg2.connect(self.connection_string)
            #logger.info("Conexão com o banco de dados estabelecida.")
            return conn
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco de dados: {e}")
            logger.error(traceback.format_exc())
            raise
        
    def add_document(self, text: str, metadata: Dict[str, Any], max_chunk_size=999999) -> List[str]:
        doc_id_list = []
        try:
            chunks = [text[i:i + max_chunk_size] for i in range(0, len(text), max_chunk_size)]
            logger.info(f"Documento dividido em {len(chunks)} chunks.")

            for idx, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                chunk_metadata = dict(metadata)
                chunk_metadata["chunk_index"] = idx
                chunk_metadata["parent_id"] = metadata.get("parent_id") or str(uuid.uuid4())

                embedding = self.embed(chunk)
                if not embedding:  # se embedding falhar ou não for 768 dimensões
                    logger.error(f"Abortando processamento. Erro ao gerar embedding do chunk {idx}.")
                    return []  # sai da função inteira

                vector_str = "[" + ",".join(map(str, embedding)) + "]"

                try:
                    conn = self._get_connection()
                    cur = conn.cursor()
                    sql = f"""
                        INSERT INTO {self.table_name} (id, text, metadata, embedding)
                        VALUES (%s, %s, %s::jsonb, %s::vector)
                        ON CONFLICT (id) DO UPDATE
                        SET text = EXCLUDED.text,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                    """
                    cur.execute(sql, (chunk_id, chunk, json.dumps(chunk_metadata), vector_str))
                    conn.commit()
                    logger.info(f"Chunk {idx} (ID: {chunk_id}) adicionado/atualizado com sucesso.")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Erro ao adicionar chunk {idx} ao banco de dados: {e}")
                    logger.error(traceback.format_exc())
                    return []  # encerra a função inteira
                finally:
                    cur.close()
                    conn.close()

                doc_id_list.append(chunk_id)

            return doc_id_list
        except Exception as e:
            logger.error(f"Erro geral no método add_document: {e}")
            logger.error(traceback.format_exc())
            return []


    def get_documents_by_user(self, user_id: str) -> List[Document]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            sql = f"SELECT id, text, metadata FROM {self.table_name} WHERE metadata->>'user_id' = %s"
            cur.execute(sql, (user_id,))
            results = cur.fetchall()
            
            documents = []
            for doc_id, text, metadata_json in results:
                metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                metadata["id"] = doc_id
                doc = Document(page_content=text, metadata=metadata)
                documents.append(doc)
            
            cur.close()
            conn.close()
            #logger.info(f"Encontrados {len(documents)} documentos para o usuário {user_id}")
            return documents
        except Exception as e:
            logger.error(f"Erro ao buscar documentos do usuário {user_id}: {e}")
            logger.error(traceback.format_exc())
            return []
        
    def delete_document(self, doc_id: str):
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(f"DELETE FROM {self.table_name} WHERE id = %s", (doc_id,))
            conn.commit()
            logger.info(f"Documento com ID {doc_id} removido com sucesso.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao remover documento com ID {doc_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            cur.close()
            conn.close()

    def search(self, query: str, filter: Dict[str, Any] = None, k: int = 25) -> List[Document]:
        try:
            docs_with_scores = self.search_with_score(query, filter, k)
            return [doc for doc, _ in docs_with_scores]
        except Exception as e:
            logger.error(f"Erro ao realizar a busca: {e}")
            logger.error(traceback.format_exc())
            return []

    def search_with_score(self, query: str, filter: Dict[str, Any] = None, k: int = 5,
                          score_threshold: float = None) -> List[Tuple[Document, float]]:
        if not query:
            logger.warning("Consulta vazia fornecida. Retornando lista vazia.")
            return []

        try:
            query_embedding = self.embed(query)
            vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

            conn = self._get_connection()
            cur = conn.cursor()

            sql = f"""
                SELECT id, text, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {self.table_name}
                WHERE 1=1
            """
            params = [vector_str]

            if filter:
                for key, value in filter.items():
                    sql += f" AND metadata->> %s = %s"
                    params.extend([key, value])

            if score_threshold is not None:
                sql += " AND (1 - (embedding <=> %s::vector)) >= %s"
                params.extend([vector_str, score_threshold])

            sql += " ORDER BY similarity DESC LIMIT %s"
            params.append(k)
            
            cur.execute(sql, params)
            results = cur.fetchall()

            docs_with_scores = []
            for doc_id, text, metadata_json, similarity in results:
                
                print(f"Arquivo encontrado na busca: {metadata_json.get('sourceFile', 'desconhecido')}")
                metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                metadata["id"] = doc_id
                doc = Document(page_content=text, metadata=metadata)
                docs_with_scores.append((doc, similarity))

            logger.info(f"Busca vetorial realizada com sucesso. Encontrados {len(results)} resultados.")
            return docs_with_scores

        except Exception as e:
            logger.error(f"Erro ao realizar busca vetorial: {e}")
            logger.error(traceback.format_exc())
            return []
        finally:
            cur.close()
            conn.close()

class PostgresRetriever(BaseRetriever, BaseModel):
    store: PgVectorStore
    search_kwargs: Dict[str, Any] = Field(default_factory=lambda: {"k": 5})

    def _get_relevant_documents(self, query: str) -> List[Document]:
        try:
            return self.store.search(
                query=query,
                filter=self.search_kwargs.get("filter"),
                k=self.search_kwargs.get("k", 5)
            )
        except Exception as e:
            logger.error(f"Erro no retriever ao buscar documentos: {e}")
            logger.error(traceback.format_exc())
            return []

    def search_with_score(self, query: str) -> List[Tuple[Document, float]]:
        try:
            return self.store.search_with_score(
                query=query,
                filter=self.search_kwargs.get("filter"),
                k=self.search_kwargs.get("k", 5),
                score_threshold=self.search_kwargs.get("score_threshold")
            )
        except Exception as e:
            logger.error(f"Erro no retriever ao buscar documentos com score: {e}")
            logger.error(traceback.format_exc())
            return []