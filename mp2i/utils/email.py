import logging
import os
import random
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

logger: logging.Logger = logging.getLogger(__name__)

__smtp_host: Optional[str] = os.getenv("MP2I__SMTP_HOST")
__smtp_port: Optional[str] = os.getenv("MP2I__SMTP_PORT")
__smtp_user: Optional[str] = os.getenv("MP2I__SMTP_USER")
__smtp_passwd: Optional[str] = os.getenv("MP2I__SMTP_PASSWD")

__context: Optional[ssl.SSLContext] = None

if not (__smtp_host and __smtp_port and __smtp_user and __smtp_passwd):
    logger.error("Email is not configured well")
else:
    __context = ssl.create_default_context()


def verification_code_generator(hardness: int) -> str:
    return f"{{:0{hardness}d}}".format(random.randint(1, 10**hardness))


def send_email(mail: str, subject: str, content: str) -> bool:
    if not __context:
        logger.error("SSL context is not defined to send mails.")
        return False
    if not (__smtp_host and __smtp_port and __smtp_user and __smtp_passwd):
        logger.error("Email is not configured well but this should ne been reached")
        return False

    email: EmailMessage = EmailMessage()
    email["Subject"] = subject
    email["From"] = __smtp_user
    email["To"] = mail
    email.set_content(content)
    try:
        with smtplib.SMTP_SSL(__smtp_host, int(__smtp_port), context=__context) as smtp:
            smtp.login(__smtp_user, __smtp_passwd)
            smtp.send_message(email)
            return True
    except Exception as err:
        logger.error("Could not send mail", err, exc_info=True)
    return False
