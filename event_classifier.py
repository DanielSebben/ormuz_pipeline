"""
Camada 3a - Classificacao de severidade dos eventos.

Duas etapas, para controlar custo e latencia:
  1) Regras por palavra-chave (gratis, roda em qualquer volume).
  2) Refinamento por LLM (Claude), so para manchetes que ja passaram
     de um limiar minimo na etapa 1 -- e onde nuance de linguagem
     importa (ex: distinguir ameaca retorica de ataque confirmado).

Tiers de severidade (calibrados nos eventos de 2026 discutidos):
  0 = ruido / nada relevante
  1 = sinal de desescalada (negociacao, cessar-fogo, retomada de transito)
  2 = ameaca ou incidente nao confirmado (aviso, deteccao, retorica)
  3 = ataque ou incidente confirmado (navio atingido, drone, mina)
  4 = fechamento de rota / guerra em curso
"""

from __future__ import annotations

import json
from dataclasses import dataclass

RULES: dict[int, list[str]] = {
    4: ["closure", "closed strait", "war", "invasion", "estreito fechado", "guerra"],
    3: [
        "attack", "strike", "missile", "drone", "mine", "explosion",
        "hit by", "fired upon", "ataque", "atingid", "míssil", "drone",
        "explos",
    ],
    2: [
        "threat", "warning", "seize", "detain", "block", "tension",
        "ameaça", "alerta", "apreens", "tensão", "advertência",
    ],
    1: [
        "ceasefire", "talks", "agreement", "deal", "reopen", "transit resumed",
        "de-escalat", "cessar-fogo", "negociaç", "reabr", "acordo",
    ],
}


@dataclass
class Classification:
    tier: int
    matched_keywords: list[str]
    source: str  # "rules" ou "llm"
    rationale: str | None = None


def classify_headline_rule_based(title: str) -> Classification:
    text = (title or "").lower()
    for tier in sorted(RULES.keys(), reverse=True):
        matched = [kw for kw in RULES[tier] if kw.lower() in text]
        if matched:
            return Classification(tier=tier, matched_keywords=matched, source="rules")
    return Classification(tier=0, matched_keywords=[], source="rules")


LLM_SYSTEM_PROMPT = """Voce e um analista de risco geopolitico especializado no \
Estreito de Ormuz e no mercado de petroleo. Dado um titulo de noticia, classifique \
a severidade em uma escala de 0 a 4:
0 = ruido, sem relevancia para o mercado de petroleo
1 = sinal de desescalada (negociacao, cessar-fogo, reabertura de rota)
2 = ameaca ou incidente nao confirmado
3 = ataque ou incidente confirmado contra navio/infraestrutura
4 = fechamento de rota ou guerra em curso
Responda SOMENTE com JSON no formato:
{"tier": <int>, "rationale": "<uma frase curta>"}"""


def classify_with_claude(title: str, api_key: str, model: str = "claude-sonnet-4-6") -> Classification:
    """
    Refinamento opcional via API da Anthropic. So chame isto para
    manchetes que ja tenham tier >= 2 na classificacao por regras --
    economiza custo e reserva o LLM para os casos que exigem leitura
    de contexto/nuance.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=200,
        system=LLM_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": title}],
    )
    raw_text = "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    )
    try:
        parsed = json.loads(raw_text.strip().strip("`"))
        return Classification(
            tier=int(parsed["tier"]),
            matched_keywords=[],
            source="llm",
            rationale=parsed.get("rationale"),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Se o parsing falhar, mantenha o resultado das regras em vez de quebrar o pipeline.
        return Classification(tier=0, matched_keywords=[], source="llm_parse_failed", rationale=raw_text)


def classify_headlines(
    headlines: list[dict], anthropic_api_key: str | None = None, llm_threshold: int = 2
) -> list[dict]:
    """Aplica a classificacao a uma lista de manchetes (dicts com chave 'title')."""
    results = []
    for h in headlines:
        rule_result = classify_headline_rule_based(h.get("title", ""))
        final = rule_result
        if anthropic_api_key and rule_result.tier >= llm_threshold:
            try:
                final = classify_with_claude(h["title"], anthropic_api_key)
            except Exception:
                final = rule_result  # cai para o resultado de regras se a chamada LLM falhar
        results.append({**h, "classification": final})
    return results


if __name__ == "__main__":
    sample = [
        {"title": "Tanker hit by projectiles crossing Strait of Hormuz, UKMTO says"},
        {"title": "Iran and Oman reach deal to regulate Hormuz transit"},
        {"title": "Local football match postponed due to rain"},
    ]
    for r in classify_headlines(sample):
        c = r["classification"]
        print(f"tier={c.tier} ({c.source}) -> {r['title']}")
