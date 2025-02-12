from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import Dict, Any
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER=Path(__file__).parent / "email_templates",
)

fastmail = FastMail(conf)


async def send_verification_email(email: EmailStr, token: str) -> None:
    """Send verification email to user"""
    frontend_url = os.getenv("FRONTEND_URL")
    verification_url = f"{frontend_url}/verify-email/{token}"

    message = MessageSchema(
        subject="Verify your Tubify account",
        recipients=[email],
        template_body={
            "verification_url": verification_url,
        },
        subtype="html",
    )

    await fastmail.send_message(message, template_name="verification.html")


async def send_password_reset_email(email: EmailStr, token: str) -> None:
    """Send password reset email to user"""
    frontend_url = os.getenv("FRONTEND_URL")
    reset_url = f"{frontend_url}/reset-password/{token}"

    message = MessageSchema(
        subject="Reset your Tubify password",
        recipients=[email],
        template_body={
            "reset_url": reset_url,
        },
        subtype="html",
    )

    await fastmail.send_message(message, template_name="reset_password.html")
