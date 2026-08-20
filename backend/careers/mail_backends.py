"""Email backend that forces the SMTP connection over IPv4.

Render's containers have no outbound IPv6 route, but smtp.gmail.com
publishes both an A and an AAAA record. Python's socket.create_connection
tries the addresses getaddrinfo returns in order — IPv6 first, per RFC
6724 — and that attempt fails instantly with
OSError: [Errno 101] Network is unreachable: a local routing-table gap,
not Gmail refusing anything. (Truehost's mail server has no AAAA record
at all, which is why direct-to-Truehost never hit this.) Resolving to
IPv4 explicitly here sidesteps the gap regardless of which provider
EMAIL_HOST ends up pointing at.

SMTP_SSL._get_socket() itself calls super()._get_socket() for the raw TCP
socket and then wraps it in TLS — the raw-connect override below has to
sit between SMTP_SSL and SMTP in the MRO so that super() call resolves to
it instead of the original, or the SSL wrapping step gets skipped
entirely. That's the reason for the multiple-inheritance shape here rather
than something simpler.
"""
import smtplib
import socket

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as _DjangoSMTPEmailBackend


class _IPv4RawSMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        if timeout is not None and not timeout:
            raise OSError('Non-blocking socket (timeout=0) is not supported')
        family, socktype, proto, _, sockaddr = socket.getaddrinfo(
            host, port, socket.AF_INET, socket.SOCK_STREAM
        )[0]
        sock = socket.socket(family, socktype, proto)
        try:
            if timeout is not None:
                sock.settimeout(timeout)
            if self.source_address:
                sock.bind(self.source_address)
            sock.connect(sockaddr)
            return sock
        except OSError:
            sock.close()
            raise


class IPv4SMTP(_IPv4RawSMTP):
    pass


class IPv4SMTP_SSL(smtplib.SMTP_SSL, _IPv4RawSMTP):
    pass


class EmailBackend(_DjangoSMTPEmailBackend):
    # Django's own connection_class is a read-only @property computed from
    # self.use_ssl (see django/core/mail/backends/smtp.py) — not a plain
    # instance attribute — so it has to be overridden the same way, not
    # assigned to in __init__.
    @property
    def connection_class(self):
        return IPv4SMTP_SSL if self.use_ssl else IPv4SMTP


# --- Resend (HTTPS API) backend -------------------------------------------
#
# Forcing IPv4 fixed the IPv6-routing-gap failure above, but a follow-up
# test on port 587 with IPv4 forced still failed — this time with a plain
# connection timeout (a SYN went out, nothing ever came back), not
# "unreachable". That's the signature of a firewall silently dropping
# packets on that port rather than there being no route at all, and it
# matches Truehost (port 465) and Gmail (587 and 465) all failing in three
# different ways from the same platform. The common thread across all of
# them is "outbound SMTP from Render doesn't work", not any one host, port,
# or IP family — so this sends over HTTPS instead, which isn't blocked.
class ResendBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(**kwargs)
        self.fail_silently = fail_silently

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        resend.api_key = settings.RESEND_API_KEY
        sent = 0
        for message in email_messages:
            html = next(
                (alt.content for alt in getattr(message, 'alternatives', [])
                 if alt.mimetype == 'text/html'),
                None,
            )
            params = {
                'from': message.from_email,
                'to': list(message.to),
                'subject': message.subject,
                'text': message.body,
            }
            if html:
                params['html'] = html
            if message.cc:
                params['cc'] = list(message.cc)
            if message.bcc:
                params['bcc'] = list(message.bcc)
            if message.reply_to:
                params['reply_to'] = list(message.reply_to)

            try:
                resend.Emails.send(params)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise

        return sent
