import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def enviar_correo(destinatarios: list, asunto: str, html: str) -> bool:
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print("SMTP_EMAIL/SMTP_APP_PASSWORD no configurados; correo no enviado:", asunto)
        return False
    if not destinatarios:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"Expediente <{SMTP_EMAIL}>"
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, destinatarios, msg.as_string())
        return True
    except Exception as e:
        print("Error al enviar correo por SMTP:", e)
        return False
