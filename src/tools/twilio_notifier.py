import structlog
from langchain_core.tools import tool
from twilio.rest import Client as TwilioClient

from src.config import settings

logger = structlog.get_logger()

_twilio_client = None


def _get_twilio_client() -> TwilioClient:
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioClient(
            settings.twilio_account_sid, settings.twilio_auth_token
        )
    return _twilio_client


@tool
async def send_sms_notification(phone_number: str, message: str) -> str:
    """Send an SMS notification to a customer's phone number.

    Args:
        phone_number: The recipient phone number in E.164 format (e.g. +15551234567).
        message: The text message body to send (max 1600 chars).
    """
    if not phone_number.startswith("+"):
        return (
            f"Invalid phone number format '{phone_number}'. "
            "Use E.164 format like +15551234567."
        )

    if len(message) > 1600:
        return "Message body exceeds the 1600 character SMS limit. Please shorten it."

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("twilio_not_configured")
        return (
            "SMS notification could not be sent: Twilio credentials are not configured. "
            "The message content was logged for follow-up."
        )

    try:
        client = _get_twilio_client()
        sms = client.messages.create(
            body=message,
            from_=settings.twilio_from_number,
            to=phone_number,
        )
        logger.info(
            "sms_sent",
            sid=sms.sid,
            to=phone_number,
            status=sms.status,
        )
        return (
            f"SMS sent successfully.\n"
            f"  SID: {sms.sid}\n"
            f"  To: {phone_number}\n"
            f"  Status: {sms.status}"
        )
    except Exception as exc:
        logger.error("sms_failed", to=phone_number, error=str(exc))
        return f"Failed to send SMS to {phone_number}: {exc}"
