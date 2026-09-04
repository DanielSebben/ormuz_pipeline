"""
Camada 4b - Notificacoes.

Tres opcoes prontas, do mais simples ao mais configuravel:

1) ntfy.sh -- zero cadastro. Voce so escolhe um "topico" (uma string
   qualquer, de preferencia dificil de adivinhar) e se inscreve nele
   pelo app ntfy (Android/iOS) ou pelo navegador. Bom para comecar hoje.

2) Telegram -- exige criar um bot gratuito com o @BotFather e pegar seu
   chat_id, mas manda a notificacao direto no seu Telegram.

3) Slack / Discord -- se voce ja usa um desses para acompanhar o
   mercado, um webhook de canal recebe o alerta em texto.

Todas as funcoes retornam True/False e nunca lancam excecao para nao
derrubar o pipeline por causa de um alerta que falhou.
"""

from __future__ import annotations

import requests


def send_ntfy(message: str, topic: str, title: str | None = None, priority: str = "default") -> bool:
    """priority: 'min' | 'low' | 'default' | 'high' | 'urgent'."""
    try:
        headers = {"Priority": priority}
        if title:
            headers["Title"] = title.encode("ascii", "ignore").decode() or "Alerta"
        resp = requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=10)
        return resp.ok
    except requests.RequestException:
        return False


def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        return resp.ok
    except requests.RequestException:
        return False


def send_slack_webhook(message: str, webhook_url: str) -> bool:
    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        return resp.ok
    except requests.RequestException:
        return False


def send_discord_webhook(message: str, webhook_url: str) -> bool:
    try:
        resp = requests.post(webhook_url, json={"content": message}, timeout=10)
        return resp.ok
    except requests.RequestException:
        return False


def dispatch_alert(message: str, config: dict) -> dict:
    """
    Dispara para todos os canais configurados em `config` (um dict lido
    das variaveis de ambiente -- veja pipeline.py). Retorna um relatorio
    de quem recebeu com sucesso.
    """
    results = {}

    if config.get("ntfy_topic"):
        results["ntfy"] = send_ntfy(message, config["ntfy_topic"], title="Alerta Irã/Ormuz")

    if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
        results["telegram"] = send_telegram(message, config["telegram_bot_token"], config["telegram_chat_id"])

    if config.get("slack_webhook_url"):
        results["slack"] = send_slack_webhook(message, config["slack_webhook_url"])

    if config.get("discord_webhook_url"):
        results["discord"] = send_discord_webhook(message, config["discord_webhook_url"])

    if not results:
        results["nenhum_canal_configurado"] = False

    return results
