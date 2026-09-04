"""
Teste rapido de notificacao -- confirma se Telegram/ntfy/Slack/Discord
estao configurados certinho, sem precisar esperar um evento real de
tier alto.

Uso:
    python test_notifier.py
"""

from dotenv import load_dotenv

from notifier import dispatch_alert
from pipeline import get_notifier_config

load_dotenv()

message = "Teste do pipeline Ormuz: se voce recebeu isso, a notificacao esta funcionando!"
result = dispatch_alert(message, get_notifier_config())

print("Resultado do teste:", result)
if any(v is True for v in result.values()):
    print("\nEnvio confirmado! Confira seu celular/app agora.")
else:
    print("\nNenhum canal confirmou o envio. Revise as chaves no .env")
    print("(e, no caso do ntfy, confirme que voce esta inscrito no topico certo em https://ntfy.sh/SEU_TOPICO).")