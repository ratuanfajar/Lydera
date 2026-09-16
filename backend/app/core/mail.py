from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import aiosmtplib
from app.core.config import email_settings 

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

async def send_otp_email_async(to_email: str, otp_code: str):
    html_template = jinja_env.get_template("otp.html")
    txt_template = jinja_env.get_template("otp.txt")

    context = {"otp_code": otp_code, "app_name": email_settings.EMAIL_FROM_NAME}
    html_content = html_template.render(**context)
    txt_content = txt_template.render(**context)

    message = MIMEMultipart("alternative")
    message["From"] = f"{email_settings.EMAIL_FROM_NAME} <{email_settings.EMAIL_FROM}>"
    message["To"] = to_email
    message["Subject"] = f"{otp_code} is your verification code"

    message.attach(MIMEText(txt_content, "plain", "utf-8"))
    message.attach(MIMEText(html_content, "html", "utf-8"))

    await aiosmtplib.send(
        message,
        hostname=email_settings.SMTP_HOST,
        port=email_settings.SMTP_PORT,
        username=email_settings.SMTP_USER,
        password=email_settings.SMTP_PASS,
        start_tls=email_settings.SMTP_TLS,
    )