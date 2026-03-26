import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
import httpx
import structlog

from worker.config import get_settings
from worker.models import PriceAlert, PriceObservation, Product

logger = structlog.get_logger(__name__)
settings = get_settings()


async def send_email_notification(subject: str, body: str) -> bool:
    """Send email notification via SMTP."""
    if not settings.smtp_host or not settings.notification_email:
        logger.debug("Email notifications not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.smtp_from or settings.smtp_user
        msg['To'] = settings.notification_email
        msg['Subject'] = f"[FilamentFinder] {subject}"
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        
        logger.info("Email notification sent", subject=subject)
        return True
        
    except Exception as e:
        logger.error("Failed to send email notification", error=str(e))
        return False


async def send_webhook_notification(subject: str, body: str) -> bool:
    """Send notification via webhook."""
    if not settings.webhook_url:
        logger.debug("Webhook notifications not configured")
        return False
    
    try:
        payload = {
            "event": "price_change",
            "subject": subject,
            "body": body,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        }
        
        headers = {"Content-Type": "application/json"}
        if settings.webhook_secret:
            import hmac
            import hashlib
            import json
            signature = hmac.new(
                settings.webhook_secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.webhook_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        
        logger.info("Webhook notification sent", subject=subject)
        return True
        
    except Exception as e:
        logger.error("Failed to send webhook notification", error=str(e))
        return False


async def send_notification(
    subject: str,
    body: str,
    *,
    use_email: bool = True,
    use_webhook: bool = True,
) -> bool:
    """Send notification via selected channels."""
    logger.info(
        "Sending notification",
        subject=subject,
        use_email=use_email,
        use_webhook=use_webhook,
    )
    
    email_sent = await send_email_notification(subject, body) if use_email else False
    webhook_sent = await send_webhook_notification(subject, body) if use_webhook else False
    
    if not email_sent and not webhook_sent:
        logger.info(
            "No notification channels configured or enabled",
            subject=subject,
            body=body,
        )
    
    return email_sent or webhook_sent


async def trigger_price_alerts(
    db,
    product: Product,
    observation: PriceObservation,
) -> int:
    if observation.price_amount is None:
        return 0

    query = db.query(PriceAlert).filter(
        PriceAlert.product_id == product.id,
        PriceAlert.active == True,
        PriceAlert.target_price >= observation.price_amount,
    )
    if observation.currency:
        query = query.filter(PriceAlert.currency == observation.currency)

    alerts = query.all()
    if not alerts:
        return 0

    for alert in alerts:
        await send_notification(
            subject=f"Price alert triggered for {product.name}",
            body=(
                f"{product.name} is now {observation.currency or ''} {float(observation.price_amount):.2f} "
                f"at {product.source.name if product.source else 'the source'}, meeting your alert target of "
                f"{alert.currency} {float(alert.target_price):.2f}."
            ).strip(),
        )
        alert.triggered_at = datetime.now(timezone.utc)
        alert.active = False

    return len(alerts)
