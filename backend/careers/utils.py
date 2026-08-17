from typing import Iterable, Optional
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from .models import NewsletterSubscriber


def send_newsletter(
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    recipients: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
):
    """Send a newsletter to active subscribers.

    - `recipients`: optional explicit list of emails. If None, send to all active subscribers.
    - `limit`: optional cap on recipients (for testing).
    - `dry_run`: if True, don't actually send, just return the list that would be sent.
    Returns list of recipients the function attempted to send to.
    """

    if recipients is None:
        qs = NewsletterSubscriber.objects.filter(is_active=True).order_by('-subscribed_at')
        emails = list(qs.values_list('email', flat=True))
    else:
        emails = list(recipients)

    if limit is not None:
        emails = emails[:limit]

    if dry_run:
        return emails

    backend = settings.MAILERS.get('default', {}).get('BACKEND') if hasattr(settings, 'MAILERS') else None
    connection = get_connection(backend=backend) if backend else get_connection()

    messages = []
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None

    for to in emails:
        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[to], connection=connection)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        messages.append(msg)

    if messages:
        connection.send_messages(messages)

    return emails
