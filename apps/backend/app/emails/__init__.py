from app.core.config import Settings
from app.emails.sender import EmailSender, SendGridSender, SuppressedSender


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.sendgrid_api_key and settings.email_from_address:
        return SendGridSender(
            api_key=settings.sendgrid_api_key,
            from_address=settings.email_from_address,
            from_name=settings.email_from_name,
            reply_to=settings.email_reply_to,
        )
    return SuppressedSender()
