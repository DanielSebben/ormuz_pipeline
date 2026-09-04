"""
Camada 2 - Radar OSINT: GDELT (fonte primaria, gratuita e sem login).

GDELT 2.0 DOC API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
Endpoint: https://api.gdeltproject.org/api/v2/doc/doc

Nao existe API oficial da UKMTO (ver nota em ukmto_notes.md). Por isso o
sinal maritimo aqui vem de forma indireta: procuramos, dentro do proprio
GDELT, noticias de agencias (Reuters, AP, etc.) que citam UKMTO, o que
cobre o mesmo evento sem depender de scraping do site da UKMTO -- que
bloqueia rastreadores automatizados via Cloudflare.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

HORMUZ_QUERY = (
    '(Hormuz OR "Strait of Hormuz") '
    '(Iran OR tanker OR attack OR missile OR drone OR mine OR UKMTO OR ceasefire OR strike)'
)


@dataclass
class GdeltSignal:
    fetched_at: float
    headlines: list = field(default_factory=list)
    coverage_timeline: list = field(default_factory=list)
    error: str | None = None


def _get(params: dict, retries: int = 3, timeout: int = 30) -> dict:
    params = {**params, "format": "json"}
    last_exc: requests.RequestException | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(GDELT_DOC_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(3 * attempt)
    raise last_exc


def get_hormuz_headlines(timespan: str = "1h", max_records: int = 50) -> list[dict]:
    data = _get(
        {
            "query": HORMUZ_QUERY,
            "mode": "artlist",
            "timespan": timespan,
            "maxrecords": max_records,
            "sort": "datedesc",
        }
    )
    articles = data.get("articles", [])
    return [
        {
            "title": a.get("title"),
            "url": a.get("url"),
            "domain": a.get("domain"),
            "seendate": a.get("seendate"),
            "tone": a.get("tone"),
            "language": a.get("language"),
        }
        for a in articles
    ]


def get_hormuz_coverage_timeline(timespan: str = "7d") -> list[dict]:
    data = _get(
        {
            "query": HORMUZ_QUERY,
            "mode": "timelinevol",
            "timespan": timespan,
        }
    )
    timeline = data.get("timeline", [])
    if not timeline:
        return []
    series = timeline[0].get("data", [])
    return [{"date": p.get("date"), "value": p.get("value")} for p in series]


def build_gdelt_signal(timespan_headlines: str = "1h", timespan_timeline: str = "7d") -> GdeltSignal:
    signal = GdeltSignal(fetched_at=time.time())
    try:
        signal.headlines = get_hormuz_headlines(timespan=timespan_headlines)
        signal.coverage_timeline = get_hormuz_coverage_timeline(timespan=timespan_timeline)
    except requests.RequestException as exc:
        signal.error = str(exc)
    return signal


if __name__ == "__main__":
    sig = build_gdelt_signal()
    if sig.error:
        print("Erro ao consultar GDELT:", sig.error)
    else:
        print(f"{len(sig.headlines)} manchetes encontradas na ultima hora.")
        for h in sig.headlines[:5]:
            print("-", h["title"], f"({h['domain']})")