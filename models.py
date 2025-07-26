# models.py

from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class Clube:
    """
    Representa um clube de futebol no sistema.
    Mapeia a tabela 'Clube' do banco de dados.
    """
    id: Optional[int] = None # ID é None para novos clubes
    nome: str = ""
    ano: Optional[date] = None # Data de fundação
    cidade: str = ""

    def to_dict(self) -> dict:
        """Converte o objeto Clube para um dicionário."""
        return {
            'id': self.id,
            'nome': self.nome,
            'ano': self.ano,
            'cidade': self.cidade
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Cria um objeto Clube a partir de um dicionário."""
        return cls(
            id=data.get('id'),
            nome=data.get('nome', ''),
            ano=data.get('ano'),
            cidade=data.get('cidade', '')
        )

@dataclass
class Elenco:
    """
    Representa um elenco de um clube em um determinado ano.
    Mapeia a tabela 'Elenco' do banco de dados.
    """
    id: Optional[int] = None # ID é None para novos elencos
    fk_clube: int = 0 # FK para Clube.ID
    ano: int = 0
    descricao: str = ""

    def to_dict(self) -> dict:
        """Converte o objeto Elenco para um dicionário."""
        return {
            'id': self.id,
            'fk_clube': self.fk_clube,
            'ano': self.ano,
            'descricao': self.descricao
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Cria um objeto Elenco a partir de um dicionário."""
        return cls(
            id=data.get('id'),
            fk_clube=data.get('fk_clube', 0),
            ano=data.get('ano', 0),
            descricao=data.get('descricao', '')
        )

@dataclass
class Jogador:
    """
    Representa um jogador de futebol.
    Mapeia a tabela 'Jogadores' do banco de dados.
    """
    id: Optional[int] = None # ID é None para novos jogadores
    elenco_id: int = 0 # FK para Elenco.ID
    nome: str = ""
    data_nascimento: Optional[date] = None
    posicao: Optional[str] = None
    nacionalidade: Optional[str] = None
    pe_dominante: Optional[str] = None # 'D' ou 'E'
    numero_partidas: int = 0
    total_minutos_jogados: int = 0
    gols_marcados: int = 0
    assistencias: int = 0

    def to_dict(self) -> dict:
        """Converte o objeto Jogador para um dicionário."""
        return {
            'id': self.id,
            'elenco_id': self.elenco_id,
            'nome': self.nome,
            'data_nascimento': self.data_nascimento,
            'posicao': self.posicao,
            'nacionalidade': self.nacionalidade,
            'pe_dominante': self.pe_dominante,
            'numero_partidas': self.numero_partidas,
            'total_minutos_jogados': self.total_minutos_jogados,
            'gols_marcados': self.gols_marcados,
            'assistencias': self.assistencias
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Cria um objeto Jogador a partir de um dicionário."""
        # Converter campos que podem vir como strings em formato de data
        data_nasc = data.get('data_nascimento')
        if isinstance(data_nasc, str):
             # Assume formato 'YYYY-MM-DD' se for string
             try:
                 data_nasc = date.fromisoformat(data_nasc)
             except ValueError:
                 data_nasc = None # Ou lançar um erro

        return cls(
            id=data.get('id'),
            elenco_id=data.get('elenco_id', 0),
            nome=data.get('nome', ''),
            data_nascimento=data_nasc,
            posicao=data.get('posicao'),
            nacionalidade=data.get('nacionalidade'),
            pe_dominante=data.get('pe_dominante'),
            numero_partidas=data.get('numero_partidas', 0),
            total_minutos_jogados=data.get('total_minutos_jogados', 0),
            gols_marcados=data.get('gols_marcados', 0),
            assistencias=data.get('assistencias', 0)
        )
