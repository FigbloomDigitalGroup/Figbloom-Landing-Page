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


from django.core.mail.backends.smtp import EmailBackend as _DjangoSMTPEmailBackend


class EmailBackend(_DjangoSMTPEmailBackend):
    # Django's own connection_class is a read-only @property computed from
    # self.use_ssl (see django/core/mail/backends/smtp.py) — not a plain
    # instance attribute — so it has to be overridden the same way, not
    # assigned to in __init__.
    @property
    def connection_class(self):
        return IPv4SMTP_SSL if self.use_ssl else IPv4SMTP
