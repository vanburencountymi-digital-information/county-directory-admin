import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> dict:
    if not to or not subject or not body:
        raise ValueError("to, subject, and body are required")
    headers = {
        "X-API-Key": settings.COUNTY_SEND_EMAIL_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"to": to, "subject": subject, "body": body}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.post(settings.WP_EMAIL_ENDPOINT, json=payload, headers=headers)
        try:
            response_body = response.json()
        except Exception:
            response_body = response.text
        if response.status_code >= 400:
            logger.error("WordPress email API error: %s", response_body)
        response.raise_for_status()
        result = response_body if isinstance(response_body, dict) else {"success": True}
        return {
            "success": result.get("success", True),
            "message": result.get("message", "Email sent successfully"),
        }
