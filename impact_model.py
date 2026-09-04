"""
Camada 3b - Motor de simulacao de impacto.

Em vez de uma "caixa preta" de agentes (tipo MiroFish), isto e um
estudo de eventos simples: uma tabela de elasticidade (faixa de
variacao % esperada por ativo, por tier de severidade) e uma
simulacao de Monte Carlo por cima dela para dar uma faixa de cenarios,
nao um numero unico e falsamente preciso.

IMPORTANTE: os ranges abaixo foram calibrados a partir de um UNICO
ciclo historico (a crise Ira/Ormuz de 2026). Isso e uma amostra
pequena -- o ideal, para um sistema de producao, e expandir a tabela
com outros choques comparaveis (Guerra dos Petroleiros nos anos 80,
Abqaiq/Fujairah 2019, invasao da Ucrania em 2022) e reestimar
periodicamente com dados novos. Trate os numeros aqui como ponto de
partida, nao como verdade calibrada.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# tier -> ativo -> (variacao_min_pct, variacao_max_pct)
ELASTICITY_TABLE: dict[int, dict[str, tuple[float, float]]] = {
    0: {},
    1: {  # desescalada / reabertura -- ex: petroleiro atravessando Ormuz em mar/2026 (-5%+)
        "brent": (-6.0, -1.5),
        "wti": (-6.0, -1.5),
        "ouro": (-1.0, -0.2),
        "petrobras": (-3.0, -0.5),
        "companhias_aereas": (1.0, 3.0),
        "usd_brl": (-1.0, 0.2),
        "btc": (-1.0, 1.5),
    },
    2: {  # ameaca / incidente nao confirmado
        "brent": (0.3, 1.5),
        "wti": (0.3, 1.5),
        "ouro": (0.1, 0.5),
        "petrobras": (0.2, 1.0),
        "companhias_aereas": (-1.0, -0.2),
        "usd_brl": (-0.2, 0.5),
        "btc": (-1.0, 1.0),
    },
    3: {  # ataque confirmado -- ex: navio-tanker atingido em 1/set/2026 (+1.7 a 2.5%)
        "brent": (1.5, 4.0),
        "wti": (1.5, 4.0),
        "ouro": (0.3, 1.0),
        "petrobras": (0.5, 2.5),
        "companhias_aereas": (-3.0, -1.0),
        "defesa": (1.0, 3.0),
        "usd_brl": (-0.3, 0.8),
        "btc": (-2.0, 1.0),
    },
    4: {  # fechamento de rota / guerra -- ex: eclosao da guerra em mar/2026 (+10%, indo a +38% ate abr)
        "brent": (8.0, 20.0),
        "wti": (8.0, 20.0),
        "ouro": (1.0, 3.0),
        "petrobras": (3.0, 8.0),
        "companhias_aereas": (-6.0, -2.0),
        "defesa": (2.0, 6.0),
        "usd_brl": (0.5, 2.0),
        "btc": (-4.0, 2.0),  # correlacao inconsistente -- ver nota abaixo
    },
}

NOTE_BTC = (
    "BTC nao tem uma reacao consistente a choques geopoliticos: ora se move como "
    "ativo de risco (cai junto com acoes), ora como 'ouro digital' (sobe como refugio). "
    "Trate o sinal de cripto com peso menor do que petroleo/cambio/acoes ate ter "
    "uma amostra historica maior."
)


@dataclass
class ImpactEstimate:
    tier: int
    ranges: dict = field(default_factory=dict)
    monte_carlo: dict = field(default_factory=dict)
    note: str = NOTE_BTC


def estimate_impact(tier: int) -> ImpactEstimate:
    ranges = ELASTICITY_TABLE.get(tier, {})
    return ImpactEstimate(tier=tier, ranges=ranges)


def run_monte_carlo(tier: int, n_sims: int = 5000, seed: int | None = None) -> dict:
    """
    Amostragem uniforme dentro do range de cada ativo, repetida n_sims
    vezes. Retorna media e um intervalo (percentil 10-90) por ativo --
    e o analogo estatisticamente honesto do que uma simulacao de
    agentes tentaria fazer, sem alegar mais precisao do que os dados
    historicos sustentam.
    """
    rng = random.Random(seed)
    ranges = ELASTICITY_TABLE.get(tier, {})
    results = {}
    for asset, (low, high) in ranges.items():
        samples = sorted(rng.uniform(low, high) for _ in range(n_sims))
        p10 = samples[int(0.10 * n_sims)]
        p50 = samples[int(0.50 * n_sims)]
        p90 = samples[int(0.90 * n_sims)]
        results[asset] = {"p10": round(p10, 2), "p50": round(p50, 2), "p90": round(p90, 2)}
    return results


if __name__ == "__main__":
    for tier in [1, 2, 3, 4]:
        print(f"\n=== Tier {tier} ===")
        for asset, stats in run_monte_carlo(tier, n_sims=2000, seed=42).items():
            print(f"  {asset:20s} p10={stats['p10']:+.2f}%  p50={stats['p50']:+.2f}%  p90={stats['p90']:+.2f}%")
