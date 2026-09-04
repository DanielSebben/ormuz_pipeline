"""
Camada 1 - Coleta de dados de mercado em tempo real.

Fontes usadas (todas oficiais/gratuitas na modalidade básica):
- EIA (eia.gov/opendata) para petroleo -> exige chave gratuita.
- yfinance (Yahoo Finance, nao oficial mas amplamente usado) para
  futuros de commodities, cambio e acoes -> sem chave.
- CoinGecko para cripto -> sem chave para uso basico.

Nenhuma dessas chamadas funciona dentro do sandbox de execucao do Claude
(a rede aqui so libera dominios como pypi/github/npm). Rode este arquivo
na sua propria maquina ou servidor.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

EIA_BASE_URL = "https://api.eia.gov/v2"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Tickers do yfinance, agrupados por categoria -- adicione/retire livremente.
# Filtrar por classe de ativo dentro do MESMO projeto = so mexer aqui,
# nao precisa de um projeto separado por tipo de ativo.
WATCHLIST: dict[str, dict[str, str]] = {
    "commodities": {
        "brent": "BZ=F",
        "wti": "CL=F",
        "gas_natural": "NG=F",
        "ouro": "GC=F",
    },
    "cambio": {
        "usd_brl": "BRL=X",
        "usd_jpy": "JPY=X",
    },
    "acoes": {
        "petrobras": "PETR4.SA",
        "exxon": "XOM",
        "ibovespa": "^BVSP",
    },
}

# Mapa reverso (nome do ativo -> categoria), usado para filtrar o snapshot.
ASSET_CATEGORY = {name: cat for cat, group in WATCHLIST.items() for name in group}

# Achatado, porque o yfinance so precisa do dicionario nome->ticker.
DEFAULT_TICKERS = {name: ticker for group in WATCHLIST.values() for name, ticker in group.items()}

DEFAULT_CRYPTO = ["bitcoin", "ethereum"]


def filter_snapshot_by_category(prices: dict, category: str) -> dict:
    """
    Filtra o snapshot de mercado por categoria: 'commodities', 'cambio',
    'acoes' ou 'cripto'. Util quando voce so quer olhar um pedaco do
    watchlist sem tocar no resto do pipeline.
    """
    if category == "cripto":
        return {"cripto": prices.get("cripto")}
    return {name: val for name, val in prices.items() if ASSET_CATEGORY.get(name) == category}


@dataclass
class MarketSnapshot:
    timestamp: float
    prices: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)


def get_oil_price_eia(api_key: str, series_id: str = "PET.RBRTE.D") -> dict | None:
    """
    Busca o preco spot de petroleo na API v2 da EIA.

    series_id padrao = Brent spot price, diario (RBRTE = Europe Brent Spot Price FOB).
    Troque para 'PET.RWTC.D' para WTI (Cushing, Oklahoma).
    Requer uma chave gratuita: https://www.eia.gov/opendata/register.php
    """
    url = f"{EIA_BASE_URL}/seriesid/{series_id}"
    try:
        resp = requests.get(url, params={"api_key": api_key}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("response", {}).get("data", [])
        if not rows:
            return None
        latest = rows[0]
        return {"date": latest.get("period"), "value_usd_bbl": latest.get("value")}
    except requests.RequestException as exc:
        return {"error": str(exc)}


def get_yfinance_snapshot(tickers: dict[str, str] | None = None) -> dict:
    """
    Busca o ultimo preco disponivel para cada ticker via yfinance.
    Import feito dentro da funcao para o modulo nao quebrar caso a
    biblioteca ainda nao esteja instalada em algum ambiente.
    """
    import yfinance as yf

    tickers = tickers or DEFAULT_TICKERS
    out = {}
    symbols = list(tickers.values())
    data = yf.download(
        symbols, period="2d", interval="1d", progress=False, group_by="ticker"
    )
    for name, symbol in tickers.items():
        try:
            if len(symbols) == 1:
                last_close = data["Close"].dropna().iloc[-1]
            else:
                last_close = data[symbol]["Close"].dropna().iloc[-1]
            out[name] = round(float(last_close), 4)
        except Exception as exc:  # dado ausente para esse ticker
            out[name] = {"error": str(exc)}
    return out


def get_crypto_snapshot(coin_ids: list[str] | None = None, vs_currency: str = "usd") -> dict:
    """Busca precos de cripto no CoinGecko (sem chave para uso basico)."""
    coin_ids = coin_ids or DEFAULT_CRYPTO
    url = f"{COINGECKO_BASE_URL}/simple/price"
    params = {"ids": ",".join(coin_ids), "vs_currencies": vs_currency}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        return {coin: raw.get(coin, {}).get(vs_currency) for coin in coin_ids}
    except requests.RequestException as exc:
        return {"error": str(exc)}


def build_market_snapshot(eia_api_key: str | None = None) -> MarketSnapshot:
    """Junta petroleo (EIA), demais ativos (yfinance) e cripto (CoinGecko)."""
    snapshot = MarketSnapshot(timestamp=time.time())

    if eia_api_key:
        oil = get_oil_price_eia(eia_api_key)
        snapshot.prices["brent_eia"] = oil
    else:
        snapshot.errors["eia"] = "EIA_API_KEY nao configurada; pulei o preco oficial de petroleo."

    try:
        snapshot.prices.update(get_yfinance_snapshot())
    except Exception as exc:
        snapshot.errors["yfinance"] = str(exc)

    snapshot.prices["cripto"] = get_crypto_snapshot()
    return snapshot


if __name__ == "__main__":
    key = os.getenv("EIA_API_KEY")
    snap = build_market_snapshot(eia_api_key=key)
    print("Snapshot:", snap.prices)
    if snap.errors:
        print("Avisos:", snap.errors)
