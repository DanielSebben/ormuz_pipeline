"""
Orquestrador do pipeline completo:
  Coleta de mercado -> Radar GDELT -> Classificacao -> Motor de impacto -> Relatorio de sinal

Uso:
    python pipeline.py

Configuracao via variaveis de ambiente (veja .env.example):
    EIA_API_KEY         opcional, para preco oficial de petroleo
    ANTHROPIC_API_KEY   opcional, para refinar a classificacao com Claude

Para rodar de forma continua, agende isto via cron (ex.: a cada 15 min)
em vez de deixar um loop infinito -- fica mais facil de monitorar,
reiniciar e limitar custo de API.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from data_sources import build_market_snapshot
from event_classifier import classify_headlines
from gdelt_client import build_gdelt_signal
from impact_model import estimate_impact, run_monte_carlo
from notifier import dispatch_alert

LOG_PATH = os.path.join(os.path.dirname(__file__), "signal_log.jsonl")

# Tier minimo para disparar notificacao (0-4, ver event_classifier.py).
# 2 = ja avisa em ameaca/incidente nao confirmado; 3 = so em ataque confirmado pra diante.
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "2"))


def run_once() -> dict:
    load_dotenv()
    eia_key = os.getenv("EIA_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    market = build_market_snapshot(eia_api_key=eia_key)
    gdelt = build_gdelt_signal(timespan_headlines="1h", timespan_timeline="7d")

    classified = []
    max_tier = 0
    if not gdelt.error:
        classified = classify_headlines(gdelt.headlines, anthropic_api_key=anthropic_key)
        tiers = [c["classification"].tier for c in classified]
        max_tier = max(tiers, default=0)

    impact = estimate_impact(max_tier)
    monte_carlo = run_monte_carlo(max_tier, n_sims=3000)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_snapshot": market.prices,
        "market_errors": market.errors,
        "gdelt_error": gdelt.error,
        "max_severity_tier": max_tier,
        "top_headlines": [
            {"title": c["title"], "tier": c["classification"].tier, "domain": c.get("domain")}
            for c in sorted(classified, key=lambda c: c["classification"].tier, reverse=True)[:5]
        ],
        "impact_ranges_pct": impact.ranges,
        "impact_monte_carlo_pct": monte_carlo,
    }
    return report


def get_notifier_config() -> dict:
    return {
        "ntfy_topic": os.getenv("NTFY_TOPIC"),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
        "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL"),
    }


def build_alert_message(report: dict) -> str:
    lines = [f"[Ormuz] Tier {report['max_severity_tier']} detectado"]
    for h in report["top_headlines"][:3]:
        lines.append(f"- {h['title']}")
    brent_range = report["impact_monte_carlo_pct"].get("brent")
    if brent_range:
        lines.append(
            f"Impacto estimado no Brent: {brent_range['p10']:+.1f}% a {brent_range['p90']:+.1f}% (mediana {brent_range['p50']:+.1f}%)"
        )
    lines.append("Isto e uma estimativa de um modelo simples, nao uma recomendacao de investimento.")
    return "\n".join(lines)


def append_to_log(report: dict) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False) + "\n")


def print_report(report: dict) -> None:
    print("=" * 70)
    print(f"Relatorio de sinal - {report['generated_at']}")
    print(f"Tier maximo de severidade detectado: {report['max_severity_tier']}")
    if report.get("gdelt_error"):
        print(f"[aviso] GDELT nao respondeu: {report['gdelt_error']}")
    if report.get("market_errors"):
        print(f"[aviso] mercado: {report['market_errors']}")
    if report["top_headlines"]:
        print("\nManchetes mais relevantes:")
        for h in report["top_headlines"]:
            print(f"  [tier {h['tier']}] {h['title']} ({h['domain']})")
    print("\nSnapshot de mercado:")
    print(json.dumps(report["market_snapshot"], indent=2, ensure_ascii=False))
    print("\nImpacto estimado (Monte Carlo, p10/p50/p90 em %):")
    print(json.dumps(report["impact_monte_carlo_pct"], indent=2, ensure_ascii=False))
    print("=" * 70)


if __name__ == "__main__":
    rep = run_once()
    print_report(rep)
    append_to_log(rep)
    print(f"\nRelatorio tambem salvo em {LOG_PATH} (historico para recalibrar o modelo depois).")

    if rep["max_severity_tier"] >= ALERT_THRESHOLD:
        alert_msg = build_alert_message(rep)
        outcome = dispatch_alert(alert_msg, get_notifier_config())
        print(f"\nTier {rep['max_severity_tier']} >= limiar ({ALERT_THRESHOLD}). Notificacao disparada: {outcome}")
    else:
        print(f"\nTier {rep['max_severity_tier']} abaixo do limiar ({ALERT_THRESHOLD}). Nenhuma notificacao enviada.")
