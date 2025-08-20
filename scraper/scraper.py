from __future__ import annotations

import argparse
import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, Dict, Iterable, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------------- Configuração de logging ------------------------- #
logger = logging.getLogger("sofascore")
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

BASE = "https://api.sofascore.com/api/v1"
TOURNAMENT_ID = 325  # Brasileirão Série A (unique-tournament)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# ------------------------- Utilidades ------------------------- #

def make_session(timeout: int = 15, total_retries: int = 5) -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=total_retries,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    s.request = _request_with_timeout(s.request, timeout)
    return s


def _request_with_timeout(orig_request, timeout: int):
    def wrapper(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return orig_request(method, url, **kwargs)

    return wrapper


def safe_get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def slugify(text: str, maxlen: int = 32) -> str:
    import re

    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:maxlen] if maxlen else text


# ------------------------- Cliente SofaScore ------------------------- #

class SofaScoreClient:
    def __init__(self, session: Optional[requests.Session] = None, pause: float = 0.4):
        self.s = session or make_session()
        self.pause = pause  # pequena pausa entre requisições

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE}{path}"
        r = self.s.get(url, params=params)
        if r.status_code != 200:
            logger.debug("GET %s -> %s", r.url, r.status_code)
        r.raise_for_status()
        sleep(self.pause)
        return r.json()

    # ---- Descoberta da temporada / rounds / eventos ---- #

    def get_seasons(self, tournament_id: int) -> List[Dict[str, Any]]:
        # /unique-tournament/{tid}/seasons
        data = self._get(f"/unique-tournament/{tournament_id}/seasons")
        return data.get("seasons", [])

    def get_season_id_by_year(self, tournament_id: int, year: int) -> Optional[int]:
        seasons = self.get_seasons(tournament_id)
        for s in seasons:
            if s.get("year") == year:
                return s.get("id")
        
        for s in seasons:
            if str(s.get("name")) == str(year):
                return s.get("id")
        return None

    def get_rounds(self, tournament_id: int, season_id: int) -> List[Dict[str, Any]]:
        # Possíveis endpoints (o SofaScore muda com o tempo)
        paths = [
            f"/unique-tournament/{tournament_id}/season/{season_id}/rounds",
            f"/unique-tournament/{tournament_id}/season/{season_id}/events/rounds",  # fallback
        ]
        for p in paths:
            try:
                data = self._get(p)
                rounds = data.get("rounds") or data.get("data") or []
                if rounds:
                    return rounds
            except requests.HTTPError:
                continue
        return []

    def get_events_by_season(self, tournament_id: int, season_id: int) -> List[Dict[str, Any]]:
        # Lista todos os jogos da temporada (todas as rodadas)
        paths = [
            f"/unique-tournament/{tournament_id}/season/{season_id}/events",
            f"/unique-tournament/{tournament_id}/season/{season_id}/matches",  # fallback
        ]
        for p in paths:
            try:
                data = self._get(p)
                events = data.get("events") or data.get("matches") or []
                if events:
                    return events
            except requests.HTTPError:
                continue
        return []

    def get_events_by_round(self, tournament_id: int, season_id: int, round_id: int) -> List[Dict[str, Any]]:
        # Retorna eventos de uma rodada específica, com múltiplos fallbacks
        candidate_paths = [
            f"/unique-tournament/{tournament_id}/season/{season_id}/round/{round_id}/events",
            f"/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round_id}",
        ]
        for p in candidate_paths:
            try:
                data = self._get(p)
                events = data.get("events") or data.get("matches") or []
                if events:
                    return events
            except requests.HTTPError:
                continue
        return []

    # ---- Detalhes da partida ---- #

    def get_event_core(self, event_id: int) -> Dict[str, Any]:
        return self._get(f"/event/{event_id}")

    def get_event_lineups(self, event_id: int) -> Dict[str, Any]:
        return self._get(f"/event/{event_id}/lineups")

    def get_event_statistics(self, event_id: int) -> Dict[str, Any]:
        return self._get(f"/event/{event_id}/statistics")

    def get_event_incidents(self, event_id: int) -> Dict[str, Any]:
        return self._get(f"/event/{event_id}/incidents")


# ------------------------- Transformação de schema ------------------------- #

@dataclass
class TeamRef:
    id: Optional[int]
    name: Optional[str]
    slug: Optional[str]


def extract_team_ref(team: Dict[str, Any]) -> TeamRef:
    return TeamRef(
        id=team.get("id"),
        name=team.get("name") or team.get("shortName"),
        slug=team.get("slug"),
    )


def flatten_team_stats(stats_payload: Dict[str, Any]) -> Dict[str, Any]:
    """A resposta de /statistics costuma vir em grupos (Attack, Passing, etc.).
    Aqui normalizamos para um dict simples por time.
    """
    out: Dict[str, Any] = {"home": {}, "away": {}}
    groups = stats_payload.get("statistics") or stats_payload.get("groups") or []
    for g in groups:
        items = g.get("statisticsItems") or g.get("items") or []
        for it in items:
            name = (it.get("name") or it.get("title") or "").strip()
            home_v = it.get("home")
            away_v = it.get("away")
            if name:
                out["home"][name] = home_v
                out["away"][name] = away_v
    # Alguns endpoints trazem xG agregado
    if "expectedGoals" in stats_payload:
        xg = stats_payload["expectedGoals"]
        out["home"]["xG"] = xg.get("home")
        out["away"]["xG"] = xg.get("away")
    return out


def lineup_to_players(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    players: List[Dict[str, Any]] = []
    if not block:
        return players
    for pl in block.get("players", []):
        player = pl.get("player") or {}
        stat = pl.get("statistics") or {}
        players.append(
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "slug": player.get("slug"),
                "shirtNumber": pl.get("shirtNumber"),
                "position": pl.get("position"),
                "captain": pl.get("captain"),
                "rating": safe_get(pl, "rating.rating") or pl.get("rating"),
                "statistics": stat or None,
            }
        )
    return players


def build_match_json(
    core: Dict[str, Any],
    lineups: Optional[Dict[str, Any]],
    statistics: Optional[Dict[str, Any]],
    incidents: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    event = core.get("event", core)  # alguns retornos aninham em {event: {...}}

    home_team = extract_team_ref(event.get("homeTeam", {}))
    away_team = extract_team_ref(event.get("awayTeam", {}))

    round_info = event.get("roundInfo") or event.get("round") or {}
    season = event.get("season") or {}
    tournament = event.get("tournament") or event.get("uniqueTournament") or {}

    # placar
    home_score = safe_get(event, "homeScore.current") or safe_get(event, "homeScore.normaltime")
    away_score = safe_get(event, "awayScore.current") or safe_get(event, "awayScore.normaltime")

    # estatísticas de time
    team_stats = flatten_team_stats(statistics) if statistics else {"home": {}, "away": {}}

    # lineups
    lu_home = safe_get(lineups or {}, "home") or {}
    lu_away = safe_get(lineups or {}, "away") or {}

    match_json: Dict[str, Any] = {
        "eventId": event.get("id"),
        "slug": event.get("slug"),
        "status": safe_get(event, "status.description") or safe_get(event, "status.type"),
        "startTimestamp": event.get("startTimestamp"),
        "referee": event.get("referee"),
        "venue": event.get("venue"),
        "round": {
            "id": round_info.get("round"),
            "name": round_info.get("name") or round_info.get("round") or None,
        },
        "season": {
            "id": season.get("id"),
            "name": season.get("name"),
            "year": season.get("year"),
        },
        "tournament": {
            "id": safe_get(tournament, "uniqueTournament.id") or tournament.get("id"),
            "name": tournament.get("name") or safe_get(tournament, "uniqueTournament.name"),
            "category": safe_get(tournament, "category.name"),
        },
        "score": {
            "home": home_score,
            "away": away_score,
            "penalties": {
                "home": safe_get(event, "homeScore.penalties"),
                "away": safe_get(event, "awayScore.penalties"),
            },
        },
        "teams": {
            "home": {
                "id": home_team.id,
                "name": home_team.name,
                "slug": home_team.slug,
                "formation": safe_get(lu_home, "formation"),
                "coach": safe_get(lu_home, "coach.name"),
                "startingXI": lineup_to_players(safe_get(lu_home, "startingLineups") or {}),
                "bench": lineup_to_players(safe_get(lu_home, "substitutes") or {}),
                "statistics": team_stats.get("home", {}),
            },
            "away": {
                "id": away_team.id,
                "name": away_team.name,
                "slug": away_team.slug,
                "formation": safe_get(lu_away, "formation"),
                "coach": safe_get(lu_away, "coach.name"),
                "startingXI": lineup_to_players(safe_get(lu_away, "startingLineups") or {}),
                "bench": lineup_to_players(safe_get(lu_away, "substitutes") or {}),
                "statistics": team_stats.get("away", {}),
            },
        },
        "incidents": (incidents or {}).get("incidents") or incidents or [],
        "raw": {
            "core": event,
            "lineups": lineups,
            "statistics": statistics,
            "incidents": incidents,
        },
    }

    return match_json


# ------------------------- Persistência ------------------------- #

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def save_match_json(base_dir: Path, match: Dict[str, Any]):
    round_id = safe_get(match, "round.id") or 0
    round_dir = base_dir / "rounds" / f"r{int(round_id):02d}"
    ensure_dir(round_dir)

    ts = match.get("startTimestamp")
    home = slugify(safe_get(match, "teams.home.slug") or safe_get(match, "teams.home.name") or "home", 16)
    away = slugify(safe_get(match, "teams.away.slug") or safe_get(match, "teams.away.name") or "away", 16)
    eid = match.get("eventId")

    fname = f"{eid}.json"
    if ts:
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        fname = f"{date_str}_r{int(round_id):02d}_{home}-vs-{away}_{eid}.json"

    out_path = round_dir / fname
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(match, f, ensure_ascii=False, indent=2)
    return out_path


def save_index(base_dir: Path, items: List[Dict[str, Any]]):
    index_path = base_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return index_path




def collect_matches(
    out_dir: Path,
    season_year: int = 2025,
    only_rounds: Optional[Tuple[int, int]] = None,
    concurrency: int = 4,
) -> List[Dict[str, Any]]:
    client = SofaScoreClient()

    logger.info("Descobrindo seasonId do ano %s…", season_year)
    season_id = 72034  
    if not season_id:
        raise RuntimeError(f"Não foi possível descobrir a season para {season_year}.")

    logger.info("seasonId = %s", season_id)

    ensure_dir(out_dir)

    # Obter rounds
    rounds = client.get_rounds(TOURNAMENT_ID, season_id)
    if not rounds:
        logger.warning("Falha ao obter rounds. Tentando varrer todos os eventos da temporada…")
        events = client.get_events_by_season(TOURNAMENT_ID, season_id)
        if not events:
            raise RuntimeError("Sem rounds e sem lista de eventos: impossível prosseguir.")
        # Extrair pseudo-rounds pelos metadados do evento
        round_map: Dict[int, List[Dict[str, Any]]] = {}
        for ev in events:
            r = safe_get(ev, "roundInfo.round") or safe_get(ev, "round.round") or 0
            round_map.setdefault(int(r), []).append(ev)
        rounds = [{"id": rid, "name": f"Round {rid}", "events": evs} for rid, evs in sorted(round_map.items())]
    else:
        # Preencher eventos por round
        for r in rounds:
            rid = r.get("id") or r.get("round")
            r["id"] = rid
            r_events = client.get_events_by_round(TOURNAMENT_ID, season_id, rid)
            if not r_events:
                # fallback: pegar todos e filtrar
                all_events = client.get_events_by_season(TOURNAMENT_ID, season_id)
                r_events = [
                    ev for ev in all_events
                    if (safe_get(ev, "roundInfo.round") or safe_get(ev, "round.round") or 0) == rid
                ]
            r["events"] = r_events

    # Filtrar por intervalo de rodadas se solicitado
    if only_rounds:
        a, b = only_rounds
        rounds = [r for r in rounds if a <= int(r.get("id", 0)) <= b]

    logger.info("Total de rodadas a processar: %d", len(rounds))

    all_index: List[Dict[str, Any]] = []

    # Processamento sequencial controlado com pequeno paralelismo por lote
    # (requests é bloqueante; manteremos simples e respeitoso com o host)
    for r in rounds:
        rid = int(r.get("id"))
        events = r.get("events", [])
        if not events:
            logger.warning("Rodada %s sem eventos.", rid)
            continue
        logger.info("Rodada %02d — %d jogos", rid, len(events))

        # processar em mini lotes para não estressar o host
        batch_size = max(1, int(concurrency))
        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]
            results: List[Tuple[Dict[str, Any], Path]] = []
            for ev in batch:
                eid = ev.get("id") or safe_get(ev, "event.id")
                if not eid:
                    continue
                try:
                    core = client.get_event_core(eid)
                    lineups = None
                    statistics = None
                    incidents = None

                    # Nem todos os endpoints existem para partidas futuras
                    try:
                        lineups = client.get_event_lineups(eid)
                    except Exception:
                        pass
                    try:
                        statistics = client.get_event_statistics(eid)
                    except Exception:
                        pass
                    try:
                        incidents = client.get_event_incidents(eid)
                    except Exception:
                        pass

                    match_json = build_match_json(core, lineups, statistics, incidents)
                    path = save_match_json(out_dir, match_json)

                    all_index.append(
                        {
                            "eventId": match_json.get("eventId"),
                            "round": rid,
                            "file": str(path.relative_to(out_dir)),
                            "home": safe_get(match_json, "teams.home.name"),
                            "away": safe_get(match_json, "teams.away.name"),
                            "startTimestamp": match_json.get("startTimestamp"),
                            "status": match_json.get("status"),
                        }
                    )
                    results.append((match_json, path))
                    logger.info("✔ %s — salvo em %s", match_json.get("slug"), path.name)
                except requests.HTTPError as http_err:
                    logger.warning("HTTP %s em event %s", getattr(http_err.response, "status_code", "?"), eid)
                except Exception as e:
                    logger.exception("Falha ao processar event %s: %s", eid, e)

    save_index(out_dir, all_index)
    logger.info("Finalizado. %d partidas salvas.", len(all_index))
    return all_index


# ------------------------- CLI ------------------------- #

def parse_rounds(arg: Optional[str]) -> Optional[Tuple[int, int]]:
    if not arg:
        return None
    if "-" in arg:
        a, b = arg.split("-", 1)
        return (int(a), int(b))
    r = int(arg)
    return (r, r)


def main():
    ap = argparse.ArgumentParser(description="Scraper SofaScore — Brasileirão 2025 (1 JSON por partida)")
    ap.add_argument("--out", default="./data/brasileirao_2025", help="Diretório de saída")
    ap.add_argument("--season-year", type=int, default=2025, help="Ano da temporada (default: 2025)")
    ap.add_argument("--rounds", type=str, default=None, help="Intervalo de rodadas, ex.: 1-38 ou 10")
    ap.add_argument("--concurrency", type=int, default=4, help="Concorrência gentil (1-6)")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    only_rounds = parse_rounds(args.rounds)

    try:
        collect_matches(out_dir, season_year=args.season_year, only_rounds=only_rounds, concurrency=args.concurrency)
    except KeyboardInterrupt:
        logger.warning("Interrompido pelo usuário.")
    except Exception:
        logger.exception("Erro fatal.")


if __name__ == "__main__":
    main()
