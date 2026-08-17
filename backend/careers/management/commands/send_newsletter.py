import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ...utils import send_newsletter


class Command(BaseCommand):
    help = 'Send a newsletter to all active subscribers (or a test email).'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Email subject')
        parser.add_argument('--body', help='Plain text body')
        parser.add_argument('--html-file', help='Path to HTML file to use as HTML body')
        parser.add_argument('--limit', type=int, help='Limit number of recipients (for testing)')
        parser.add_argument('--dry-run', action='store_true', help="Don't actually send, just show recipients")
        parser.add_argument('--test-email', help='Send only to this email (overrides recipients)')

    def handle(self, *args, **options):
        subject = options.get('subject')
        body = options.get('body') or ''
        html_file = options.get('html_file')
        limit = options.get('limit')
        dry_run = options.get('dry_run')
        test_email = options.get('test_email')

        html_body = None
        if html_file:
            if not os.path.exists(html_file):
                raise CommandError(f'HTML file not found: {html_file}')
            with open(html_file, 'r', encoding='utf-8') as fh:
                html_body = fh.read()

        recipients = [test_email] if test_email else None

        self.stdout.write('Preparing recipients...')
        sent = send_newsletter(subject=subject, text_body=body, html_body=html_body, recipients=recipients, limit=limit, dry_run=dry_run)

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Dry-run complete. Would have sent to {len(sent)} recipients:'))
            for r in sent:
                self.stdout.write(f' - {r}')
            return

        self.stdout.write(self.style.SUCCESS(f'Newsletter sent to {len(sent)} recipients'))
