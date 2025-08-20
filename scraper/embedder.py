import json
import os
import glob
import logging
from pg_vector_store import PgVectorStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SofaScoreEmbedder")

class SofaScoreEmbedder:
    def __init__(self, vector_store: PgVectorStore):
        if not isinstance(vector_store, PgVectorStore):
            raise TypeError("vector_store deve ser uma instância de PgVectorStore.")
        self.vector_store = vector_store
        logger.info("SofaScoreEmbedder inicializado.")

    def _create_player_chunk(self, player_data: dict, match_context: dict) -> tuple[dict, dict]:
        player_info = player_data.get('player', {})
        player_stats = player_data.get('statistics', {})

        chunk_content = {
            "matchInfo": {
                "eventId": match_context.get("eventId"),
                "matchDate": match_context.get("matchDate"),
                "season": match_context.get("season"),
                "round": match_context.get("round"),
                "homeTeam": match_context.get("homeTeamName"),
                "awayTeam": match_context.get("awayTeamName"),
                "finalScore": f"{match_context.get('homeScore')} x {match_context.get('awayScore')}"
            },
            "playerPerformance": {
                "playerId": player_info.get("id"),
                "playerName": player_info.get("name"),
                "playerTeam": match_context.get("playerTeamName"),
                "position": player_data.get("position"),
                "jerseyNumber": player_data.get("jerseyNumber"),
                "isSubstitute": player_data.get("substitute", False),
                "statistics": player_stats
            }
        }

        metadata = {
            "eventId": match_context.get("eventId"),
            "playerId": player_info.get("id"),
            "playerName": player_info.get("name"),
            "teamId": match_context.get("playerTeamId"),
            "teamName": match_context.get("playerTeamName"),
            "season": match_context.get("season"),
            "round": match_context.get("round"),
            "sourceFile": os.path.basename(match_context.get("sourceFile")),
            "parent_id": str(match_context.get("eventId"))
        }
        
        metadata = {k: v for k, v in metadata.items() if v is not None}
        return chunk_content, metadata

    def process_and_embed_directory(self, base_path: str):
        search_path = os.path.join(base_path, 'data')
        logger.info(f"Iniciando processo de embedding para o diretório: {search_path}")

        json_files = glob.glob(os.path.join(search_path, '**', '*.json'), recursive=True)
        total_files = len(json_files)
        logger.info(f"Encontrados {total_files} arquivos JSON para processar.")

        for i, file_path in enumerate(json_files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    match_data = json.load(f)

                # Acessa os dados brutos que contêm as informações necessárias
                raw_data = match_data.get('raw', {})
                if not raw_data:
                    logger.warning(f"Estrutura 'raw' não encontrada no arquivo {file_path}. Pulando.")
                    continue
                
                core_data = raw_data.get('core', {})
                lineups_data = raw_data.get('lineups', {})

                season_info = core_data.get('season', {})
                home_team_info = core_data.get('homeTeam', {})
                away_team_info = core_data.get('awayTeam', {})
                score_info = core_data.get('homeScore', {}), core_data.get('awayScore', {})

                base_context = {
                    "eventId": core_data.get("id"),
                    "matchDate": core_data.get("startTimestamp"),
                    "season": season_info.get("year"),
                    "round": core_data.get("roundInfo", {}).get("round"),
                    "homeTeamName": home_team_info.get("name"),
                    "awayTeamName": away_team_info.get("name"),
                    "homeScore": score_info[0].get("current"),
                    "awayScore": score_info[1].get("current"),
                    "sourceFile": file_path
                }
                
                teams_to_process = { "home": home_team_info, "away": away_team_info }
                
                players_processed_count = 0
                for team_type, team_info in teams_to_process.items():
                    players = lineups_data.get(team_type, {}).get('players', [])
                    
                    if not players:
                        continue

                    for player_data in players:
                        if not player_data.get('statistics'):
                            continue

                        player_context = base_context.copy()
                        player_context["playerTeamName"] = team_info.get("name")
                        player_context["playerTeamId"] = team_info.get("id")

                        chunk_content, metadata = self._create_player_chunk(player_data, player_context)
                        text_to_embed = json.dumps(chunk_content, indent=2, ensure_ascii=False)
                        
                        self.vector_store.add_document(text=text_to_embed, metadata=metadata)
                        players_processed_count += 1
                
                # Saída visual e limpa
                status_icon = "✅" if players_processed_count > 0 else "⚠️"
                print(f"[{i+1:04d}/{total_files}] {status_icon} | {players_processed_count:02d} chunks | {os.path.basename(file_path)}")


            except json.JSONDecodeError:
                print(f"[{i+1:04d}/{total_files}] ❌ | Erro de JSON | {os.path.basename(file_path)}")
            except Exception:
                print(f"[{i+1:04d}/{total_files}] ❌ | Erro Inesperado | {os.path.basename(file_path)}")

        logger.info("Processo de embedding concluído.")


if __name__ == '__main__':
    # O caminho base agora aponta para a pasta 'SofaScraper'
    base_project_path = '/Users/ale/Desktop/projetos/GitHub/Sofa Scraper/'

    try:
        pg_vector_store = PgVectorStore()
        embedder = SofaScoreEmbedder(vector_store=pg_vector_store)
        embedder.process_and_embed_directory(base_path=base_project_path)

    except Exception as e:
        logger.error(f"Falha ao executar o script principal: {e}", exc_info=True)
