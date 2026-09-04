# Pipeline de sinal Irã/Ormuz — petróleo, câmbio, ações e cripto

Sistema de apoio à decisão que liga notícias sobre o Irã e o Estreito de
Ormuz a uma estimativa de impacto em múltiplos ativos. **Não é
recomendação de investimento** — é uma ferramenta de triagem para você
decidir com mais informação, mais rápido.

## Arquitetura

```
data_sources.py     -> preços (petróleo via EIA, câmbio/ações/commodities
                        via yfinance, cripto via CoinGecko), organizados
                        por categoria em WATCHLIST
gdelt_client.py      -> manchetes e volume de cobertura sobre Irã/Ormuz
                        via GDELT (gratuito, sem login)
event_classifier.py  -> classifica cada manchete em tier 0-4 (regras +
                        refinamento opcional via Claude)
impact_model.py      -> tabela de elasticidade por ativo + simulação
                        Monte Carlo (faixa p10/p50/p90, não um número único)
notifier.py          -> dispara alerta por ntfy.sh, Telegram, Slack ou Discord
pipeline.py          -> orquestra tudo e decide se dispara notificação
ukmto_notes.md       -> por que não há scraping direto da UKMTO
```

Um único projeto cobre petróleo, outras commodities, câmbio, ações e
cripto — a única diferença entre eles é uma entrada no dicionário
`WATCHLIST` (`data_sources.py`). Use `filter_snapshot_by_category()`
para olhar só uma classe de ativo sem tocar no resto do pipeline.

## Instalação

```bash
pip install -r requirements.txt
cp .env.example .env
# edite o .env com as chaves que você for usar
```

Nenhuma chave é obrigatória: o que faltar vira apenas um aviso no
relatório, o resto do pipeline continua funcionando.

## Rodando uma vez

```bash
python pipeline.py
```

Isso imprime um relatório, grava uma linha em `signal_log.jsonl`
(seu histórico para recalibrar a tabela de elasticidade com o tempo)
e dispara notificação se o tier ficar ≥ `ALERT_THRESHOLD`.

## Deixando isso rodando sozinho (24h)

O script roda uma vez e termina — para virar monitoramento contínuo,
agende a execução. Duas opções:

**Opção A — cron num servidor pequeno / Raspberry Pi**
```
*/15 * * * * cd /caminho/para/ormuz_pipeline && /usr/bin/python3 pipeline.py >> cron.log 2>&1
```

**Opção B — GitHub Actions (gratuito, sem servidor próprio)**
Crie `.github/workflows/pipeline.yml` no seu repositório:
```yaml
name: ormuz-pipeline
on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python pipeline.py
        env:
          EIA_API_KEY: ${{ secrets.EIA_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
```
(Guarde as chaves em Settings → Secrets do repositório, nunca no código.)
GitHub Actions não garante o cron no minuto exato — para esse caso de
uso (verificação a cada 15 min) isso não costuma ser um problema.

## Limitações honestas

- A tabela de elasticidade em `impact_model.py` foi calibrada com **um
  único ciclo histórico** (a crise de 2026). É um começo, não uma
  calibração estatisticamente robusta — vale expandir com outros
  choques comparáveis (Guerra dos Petroleiros nos anos 80,
  Abqaiq/Fujairah 2019, invasão da Ucrânia em 2022) conforme você
  acumula seu próprio `signal_log.jsonl`.
- Notícia não é preço: existe risco de manchete falsa, exagerada ou já
  precificada antes de você agir. Trate o tier como um alerta para
  investigar, não como um gatilho automático de ordem.
- O sinal de cripto (BTC) tem correlação inconsistente com choques
  geopolíticos — peso menor do que os demais ativos.
- Isto não substitui gestão de risco básica (tamanho de posição,
  stop-loss, diversificação) nem aconselhamento financeiro
  profissional.
