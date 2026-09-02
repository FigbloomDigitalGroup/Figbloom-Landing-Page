from django.shortcuts import get_object_or_404, render, redirect
from rest_framework import generics, status, viewsets, permissions
from rest_framework.authentication import SessionAuthentication
from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import APIView, action
from .models import Job, JobApplication, NewsletterSubscriber, ContactInquiry
from .serializers import (JobSerializer, JobApplicationSerializer, NewsletterSubscriberSerializer,JobApplicationAdminSerializer, ContactInquirySerializer, ContactInquiryAdminSerializer)
from django.contrib import messages
from .forms import JobApplicationForm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.mail import EmailMultiAlternatives
from django.core import signing
from django.conf import settings
from html import escape
from email.mime.image import MIMEImage
import logging
import os
import threading

logger = logging.getLogger(__name__)
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required



@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"detail": "CSRF cookie set"})


def _load_logo_mime_image():
    """The branded-email logo, embedded inline via Content-ID rather than a
    remote URL — most mail clients block remote images by default, but an
    embedded one just shows up immediately."""
    logo_path = os.path.join(
        settings.BASE_DIR.parent, "frontend", "assets", "images", "figbloom_logo.png"
    )

    try:
        with open(logo_path, "rb") as logo_file:
            logo_bytes = logo_file.read()
    except OSError:
        return None

    logo_image = MIMEImage(logo_bytes)
    logo_image.add_header("Content-ID", "<figbloom-logo>")
    logo_image.add_header("Content-Disposition", "inline", filename="figbloom_logo.png")
    return logo_image


def build_branded_email_html(*, eyebrow, title, body_html, preheader='', footer_note_html='', footer_action_html=''):
    """Shared HTML wrapper for every outbound email (newsletter, application
    received, application withdrawn) — same header/logo/accent-bar/footer
    shell, different eyebrow/title/body/footer content per caller."""
    current_year = timezone.now().year

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">

    <title>{escape(title)}</title>
</head>

<body style="
    margin:0;
    padding:36px 16px;
    background:#eef1ee;
    font-family:Helvetica, Arial, sans-serif;
    color:#333333;
">

    <div style="
        max-width:600px;
        margin:0 auto;
    ">

        <!-- PREHEADER SPACER -->
        <div style="
            max-width:600px;
            margin:0 auto 18px;
            text-align:center;
            font-family:Arial, Helvetica, sans-serif;
            font-size:11px;
            letter-spacing:0.12em;
            text-transform:uppercase;
            color:#8a978d;
        ">
            {escape(preheader) if preheader else 'Figbloom Digital Group'}
        </div>

        <div style="
            background:#ffffff;
            border-radius:14px;
            overflow:hidden;
            border:1px solid #e3e9e2;
        ">

            <!-- HEADER -->
            <!-- White, not brand-green: the logo's "Fig" wordmark is
                 rendered in that same dark green, so a green header
                 would swallow half the logo. The PNG already spells
                 out "Figbloom Digital Group" on its own, so no
                 redundant text wordmark is added alongside it. -->

            <div style="
                background:#ffffff;
                padding:34px 30px 26px;
                text-align:center;
            ">

                <img
                    src="cid:figbloom-logo"
                    width="150"
                    alt="Figbloom Digital Group"
                    style="display:block; margin:0 auto; width:150px; max-width:60%; height:auto; border:0; outline:none;"
                />

            </div>

            <!-- ACCENT RULE -->
            <div style="height:4px; line-height:4px; font-size:0; background:#ff9400;">&nbsp;</div>


            <!-- CONTENT -->

            <div style="
                padding:44px 42px 40px;
            ">

                <div style="
                    font-family:Arial, Helvetica, sans-serif;
                    color:#ff9400;
                    font-size:12px;
                    letter-spacing:0.14em;
                    text-transform:uppercase;
                    font-weight:700;
                    margin-bottom:14px;
                ">
                    {escape(eyebrow)}
                </div>

                <h1 style="
                    margin:0 0 26px 0;
                    color:#12151e;
                    font-size:28px;
                    line-height:1.35;
                    font-weight:700;
                ">
                    {escape(title)}
                </h1>

                <div style="
                    height:1px;
                    background:#edf0ed;
                    margin:0 0 26px 0;
                "></div>

                <div style="
                    color:#3d443f;
                    font-size:16px;
                    line-height:1.85;
                ">
                    {body_html}
                </div>

            </div>


            <!-- FOOTER -->

            <div style="
                background:#f6f8f6;
                border-top:1px solid #e3e9e2;
                text-align:center;
                padding:30px 30px;
                font-family:Arial, Helvetica, sans-serif;
                color:#8a978d;
                font-size:13px;
            ">

                <div style="
                    color:#2c5322;
                    font-size:15px;
                    font-weight:700;
                    margin-bottom:6px;
                ">
                    Figbloom Digital Group
                </div>

                <div>
                    Technology &bull; Innovation &bull; Growth
                </div>

                {f'''
                <div style="
                    margin-top:14px;
                    font-size:12px;
                    line-height:1.7;
                ">
                    {footer_note_html}
                </div>
                ''' if footer_note_html else ''}

                {f'''
                <div style="
                    margin-top:16px;
                    padding-top:16px;
                    border-top:1px solid #e3e9e2;
                    font-size:12px;
                ">
                    {footer_action_html}
                </div>
                ''' if footer_action_html else ''}

                <div style="
                    margin-top:14px;
                    font-size:11px;
                    color:#a9b3ac;
                ">
                    &copy; {current_year} Figbloom Digital Group. All rights reserved.
                </div>

            </div>

        </div>

    </div>

</body>
</html>
"""


class JobListView(generics.ListAPIView):
    serializer_class = JobSerializer
    def get_queryset(self):
        return Job.objects.open().order_by('-created_at')


class JobDetailView(generics.RetrieveAPIView):
    queryset = Job.objects.open()
    serializer_class = JobSerializer
    lookup_field = 'slug'


class ApplicationCreateView(generics.CreateAPIView):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer

    def create(self, request, *args, **kwargs):
        job_id = request.data.get('job')
        email = request.data.get('email', '').strip().lower()

        if job_id and email:
            existing = JobApplication.objects.select_related('job').filter(
                job_id=job_id, email__iexact=email
            ).first()

            if existing:
                # Same credential scheme as a fresh submission below — this
                # lets a duplicate attempt recover real, live status (not
                # just a "you already applied" message) even on a browser
                # that never had the original tracking token saved.
                access_token = signing.dumps(existing.id, salt='application-access')

                return Response(
                    {
                        'detail': 'You have already applied for this position.',
                        'tracking_token': access_token,
                        'status': existing.status,
                        'status_display': existing.get_status_display(),
                        'job_title': existing.job.title,
                        'job_slug': existing.job.slug,
                        'applied_at': existing.applied_at,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()

        # This token is the applicant's only credential — no login exists —
        # so it does double duty as both the withdraw link's token and the
        # frontend's tracking key for the status-check endpoint below.
        access_token = signing.dumps(application.id, salt='application-access')
        withdraw_url = request.build_absolute_uri(f'/career/withdraw/{access_token}/')

        # Same reasoning as ContactCreateView: the application is already
        # saved, so a slow/failing SMTP send loses the confirmation email,
        # not the application. Backgrounded so the applicant isn't stuck on
        # "Submitting..." waiting on a third-party mail server.
        threading.Thread(
            target=self._notify_safely,
            args=(application, withdraw_url),
            daemon=True,
        ).start()

        return Response(
            {
                'message': 'Application submitted successfully.',
                'application': serializer.data,
                'tracking_token': access_token,
                'status': application.status,
                'status_display': application.get_status_display(),
            },
            status=status.HTTP_201_CREATED,
        )

    def _notify_safely(self, application, withdraw_url):
        try:
            self._notify(application, withdraw_url)
        except Exception:
            logger.exception('Failed to send application confirmation email')

    def _notify(self, application, withdraw_url):
        first_name = application.full_name.split(' ')[0] or application.full_name

        body_html = f"""
            <p style="margin:0 0 18px;">Hi {escape(first_name)},</p>
            <p style="margin:0 0 18px;">
                Thanks for applying for <strong>{escape(application.job.title)}</strong> at
                Figbloom Digital Group. We've received your application and our team will
                review it shortly — we'll be in touch if there's a match.
            </p>
            <p style="margin:0;">
                Changed your mind? You can withdraw your application at any time using the
                link below.
            </p>
        """

        html_content = build_branded_email_html(
            eyebrow='Application Received',
            title=f'Application received — {application.job.title}',
            preheader=f"We've received your application for {application.job.title}",
            body_html=body_html,
            footer_note_html=(
                "You're receiving this email because you applied for a position at "
                "Figbloom Digital Group."
            ),
            footer_action_html=(
                f'<a href="{withdraw_url}" style="color:#8a978d; text-decoration:underline;">'
                'Withdraw your application</a>'
            ),
        )

        message = EmailMultiAlternatives(
            subject=f'Application received — {application.job.title}',
            body=(
                f"Hi {application.full_name}, thanks for applying for {application.job.title}. "
                f"We've received your application. To withdraw it, visit: {withdraw_url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[application.email],
        )
        message.attach_alternative(html_content, 'text/html')

        logo_image = _load_logo_mime_image()
        if logo_image:
            message.attach(logo_image)

        message.send(fail_silently=False)


class ApplicationStatusView(APIView):
    """Public, read-only status lookup for an applicant's own application.

    No login exists for applicants, so the signed access token handed back
    at submission time (and embedded in the confirmation/withdrawal emails)
    is the credential — same token, same salt as withdraw_application_view.
    """

    def get(self, request):
        token = request.query_params.get('token', '')

        try:
            application_id = signing.loads(token, salt='application-access')
        except signing.BadSignature:
            return Response(
                {'detail': 'Invalid or expired tracking token.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        application = JobApplication.objects.select_related('job').filter(id=application_id).first()

        if not application:
            return Response(
                {'detail': 'Invalid or expired tracking token.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'status': application.status,
            'status_display': application.get_status_display(),
            'job_title': application.job.title,
            'job_slug': application.job.slug,
            'applied_at': application.applied_at,
        })


def apply_for_job(request, slug):
    job = get_object_or_404(Job, slug=slug, is_open=True)

    if request.method == "POST":
        form = JobApplicationForm(request.POST, request.FILES)

        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.save()

            messages.success(
                request,
                "Your application was submitted successfully."
            )

            return redirect(
                "job_detail",
                slug=job.slug
            )

    else:
        form = JobApplicationForm()

    return render(
        request,
        "career/apply.html",
        {
            "job": job,
            "form": form
        }
    )

class ChangePasswordView(APIView):

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):

        current_password = request.data.get(
            "current_password",
            ""
        )

        new_password = request.data.get(
            "new_password",
            ""
        )

        confirm_password = request.data.get(
            "confirm_password",
            ""
        )

        user = request.user


        # Check current password

        if not user.check_password(
            current_password
        ):

            return Response(
                {
                    "detail":
                        "Your current password is incorrect."
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        # Check new password confirmation

        if new_password != confirm_password:

            return Response(
                {
                    "detail":
                        "The new passwords do not match."
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        # Basic password length check

        if len(new_password) < 8:

            return Response(
                {
                    "detail":
                        "Your new password must contain at least 8 characters."
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        # Don't allow the same password

        if user.check_password(
            new_password
        ):

            return Response(
                {
                    "detail":
                        "Your new password must be different from your current password."
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        # Save new password

        user.set_password(
            new_password
        )

        user.save(
            update_fields=["password"]
        )


        # Keep the current session valid
        # until we intentionally log the user out
        update_session_auth_hash(
            request,
            user
        )


        return Response(
            {
                "detail":
                    "Password changed successfully."
            },
            status=status.HTTP_200_OK
        )

# Admin application details page
@login_required(login_url='/admin-dashboard/login')
def admin_application_detail(request):
    return render(
        request,
        "admin-dashboard/application-detail.html"
    )

@login_required(login_url='/admin-dashboard/login')
def admin_profile_settings(request):
    return render(
        request,
        "admin-dashboard/profile-settings.html",
        {"active_nav": "profile"},
    )

@login_required(login_url='/admin-dashboard/login')
def admin_subscribers(request):
    return render(
        request,
        "admin-dashboard/subscribers.html",
        {"active_nav": "subscribers"},
    )


@login_required(login_url='/admin-dashboard/login')
def admin_contact_page(request):
    return render(
        request,
        "admin-dashboard/contact.html",
        {"active_nav": "contact"},
    )

# --- Admin dashboard API ---
# All views below require an authenticated, staff-level Django user

class JobAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on jobs for the admin dashboard (create/edit/close postings)."""
    queryset = Job.objects.all().order_by('-created_at')
    serializer_class = JobSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]


class ApplicationAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on applications for the admin dashboard (view/update status)."""
    queryset = JobApplication.objects.all().order_by('-applied_at')
    serializer_class = JobApplicationAdminSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def perform_update(self, serializer):
        previous_status = serializer.instance.status
        application = serializer.save()

        # Self-service withdrawal (the applicant's own withdraw link) is a
        # separate view with its own dedicated email — this only fires for
        # status changes staff make here, so there's no double-send.
        if application.status != previous_status:
            withdraw_token = signing.dumps(application.id, salt='application-access')
            withdraw_url = self.request.build_absolute_uri(f'/career/withdraw/{withdraw_token}/')

            threading.Thread(
                target=_notify_status_change_safely,
                args=(application, withdraw_url),
                daemon=True,
            ).start()


class NewsletterAdminViewSet(viewsets.ModelViewSet):
    queryset = NewsletterSubscriber.objects.all().order_by('-subscribed_at')
    serializer_class = NewsletterSubscriberSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        """
        Filter newsletter subscribers.

        Supported filters:

        ?filter=everyone
        ?filter=today
        ?filter=yesterday
        ?filter=date&date=2026-08-10
        """

        queryset = NewsletterSubscriber.objects.filter(
            is_active=True
        ).order_by('-subscribed_at')

        filter_type = self.request.query_params.get(
            'filter',
            'everyone'
        )

        today = timezone.localdate()

        # -------------------------
        # EVERYONE
        # -------------------------

        if filter_type == 'everyone':
            return queryset

        # -------------------------
        # TODAY
        # -------------------------

        if filter_type == 'today':

            return queryset.filter(
                subscribed_at__date=today
            )

        # -------------------------
        # YESTERDAY
        # -------------------------

        if filter_type == 'yesterday':

            yesterday = today - timedelta(days=1)

            return queryset.filter(
                subscribed_at__date=yesterday
            )

        # -------------------------
        # SPECIFIC DATE
        # -------------------------

        if filter_type == 'date':

            selected_date = self.request.query_params.get(
                'date'
            )

            if not selected_date:
                return queryset.none()

            parsed_date = parse_date(selected_date)

            if not parsed_date:
                return queryset.none()

            return queryset.filter(
                subscribed_at__date=parsed_date
            )

        # Unknown filter
        return queryset

    @action(
        detail=False,
        methods=["post"],
        url_path="send",
    )
    def send_newsletter(self, request):
        subject = request.data.get("subject", "").strip()
        html_content = request.data.get("content", "").strip()

        # Get the selected date/filter from frontend
        date_filter = request.data.get("date", "everyone")

        if not subject:
            return Response(
                {"detail": "Newsletter subject is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not html_content:
            return Response(
                {"detail": "Newsletter content is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # GET ACTIVE SUBSCRIBERS
        # ---------------------------------------------------------

        subscribers = NewsletterSubscriber.objects.filter(
            is_active=True
        )

        # ---------------------------------------------------------
        # APPLY DATE FILTER
        # ---------------------------------------------------------

        today = timezone.localdate()

        if date_filter == "today":

            subscribers = subscribers.filter(
                subscribed_at__date=today
            )

        elif date_filter == "yesterday":

            yesterday = today - timedelta(days=1)

            subscribers = subscribers.filter(
                subscribed_at__date=yesterday
            )

        elif date_filter not in ["everyone", "", None]:

            # Specific date from date picker
            try:

                selected_date = parse_date(date_filter)

                if selected_date:
                    subscribers = subscribers.filter(
                        subscribed_at__date=selected_date
                    )

            except Exception:
                pass

        # ---------------------------------------------------------
        # GET EMAIL ADDRESSES
        # ---------------------------------------------------------

        recipients = list(
            subscribers.values_list(
                "id",
                "email",
            )
        )

        if not recipients:

            return Response(
                {
                    "detail": "No active subscribers found for the selected filter.",
                    "sent": 0,
                    "failed": 0,
                    "total": 0,
                },
                status=status.HTTP_200_OK,
            )

        # ---------------------------------------------------------
        # SEND EMAILS
        # ---------------------------------------------------------

        from django.core.mail import (
            EmailMultiAlternatives,
            get_connection,
        )

        from django.utils.html import strip_tags, escape

        text_content = strip_tags(html_content)

        sent = 0
        failed = 0
        failed_emails = []

        connection = get_connection(
            fail_silently=False
        )

        # ---------------------------------------------------------
        # NEWSLETTER EMAIL DESIGN
        # IMPORTANT:
        # The unsubscribe link is per-recipient (a signed token that
        # decodes to that subscriber's id), so the HTML is built once
        # per recipient inside the send loop below, not once up front.
        # ---------------------------------------------------------

        def build_email_html(unsubscribe_url):
            return build_branded_email_html(
                eyebrow='Newsletter Update',
                title=subject,
                preheader='Figbloom Digital Group • Newsletter',
                body_html=html_content.replace(chr(10), '<br>'),
                footer_note_html=(
                    "You're receiving this email because you subscribed to updates from "
                    "figbloom.org. Thank you for being part of our community."
                ),
                footer_action_html=(
                    f'<a href="{unsubscribe_url}" style="color:#8a978d; text-decoration:underline;">'
                    'Unsubscribe from this newsletter</a>'
                ),
            )

        # ---------------------------------------------------------
        # LOGO (read once here; a fresh MIMEImage is built per recipient
        # below since attaching the same MIME object across many separate
        # messages isn't safe, but re-reading the file from disk for every
        # recipient would be)
        # ---------------------------------------------------------

        logo_path = os.path.join(
            settings.BASE_DIR.parent, "frontend", "assets", "images", "figbloom_logo.png"
        )

        try:
            with open(logo_path, "rb") as logo_file:
                logo_bytes = logo_file.read()
        except OSError:
            logo_bytes = None

        # ---------------------------------------------------------
        # SEND EMAILS
        # ---------------------------------------------------------

        try:

            connection.open()

            for subscriber_id, email in recipients:

                try:

                    unsubscribe_token = signing.dumps(
                        subscriber_id,
                        salt="newsletter-unsubscribe",
                    )

                    unsubscribe_url = request.build_absolute_uri(
                        f"/unsubscribe/{unsubscribe_token}/"
                    )

                    message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[email],
                        connection=connection,
                    )

                    message.attach_alternative(
                        build_email_html(unsubscribe_url),
                        "text/html",
                    )

                    if logo_bytes:
                        # Django 6.1's EmailMessage always nests
                        # attachments under multipart/mixed (the
                        # long-standing multipart/related override via
                        # `mixed_subtype` was removed) — every major
                        # mail client still resolves a cid: reference
                        # to a sibling attachment fine either way, so
                        # this is just attach() + Content-ID.
                        logo_image = MIMEImage(logo_bytes)
                        logo_image.add_header("Content-ID", "<figbloom-logo>")
                        logo_image.add_header(
                            "Content-Disposition", "inline", filename="figbloom_logo.png"
                        )
                        message.attach(logo_image)

                    message.send(
                        fail_silently=False
                    )

                    sent += 1

                except Exception as error:

                    failed += 1

                    print(
                        f"NEWSLETTER EMAIL FAILED: {email}"
                    )

                    print(
                        f"ERROR: {repr(error)}"
                    )

                    failed_emails.append({
                        "email": email,
                        "error": str(error),
                    })

        finally:

            connection.close()

        return Response(
            {
                "detail": "Newsletter processing completed.",
                "sent": sent,
                "failed": failed,
                "total": len(recipients),
                "failed_emails": failed_emails,
            },
            status=status.HTTP_200_OK,
        )


class NewsletterSubscribeView(generics.CreateAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email', '').strip().lower()

        if not email:
            return Response(
                {'detail': 'Email address is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscriber = NewsletterSubscriber.objects.filter(
            email__iexact=email
        ).first()

        if subscriber:
            if subscriber.is_active:
                return Response(
                    {'detail': 'You are already subscribed.'},
                    status=status.HTTP_200_OK
                )

            subscriber.is_active = True
            subscriber.save(update_fields=['is_active'])

            return Response(
                {'detail': 'Your subscription has been reactivated.'},
                status=status.HTTP_200_OK
            )

        serializer = self.get_serializer(
            data={
                'email': email,
                'is_active': True,
            }
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'detail': 'Successfully subscribed to our newsletter.'},
            status=status.HTTP_201_CREATED
        )


def unsubscribe_view(request, token):
    """One-click unsubscribe link embedded in every newsletter email.

    No login is required — the token itself (a signed subscriber id) is
    the credential, the same pattern Django uses for password-reset
    links. No expiry is set: an unsubscribe link in a two-year-old email
    should still work.
    """
    try:
        subscriber_id = signing.loads(token, salt='newsletter-unsubscribe')
    except signing.BadSignature:
        return render(
            request,
            'unsubscribe/index.html',
            {'state': 'invalid'},
        )

    subscriber = NewsletterSubscriber.objects.filter(id=subscriber_id).first()

    if not subscriber:
        return render(
            request,
            'unsubscribe/index.html',
            {'state': 'invalid'},
        )

    if subscriber.is_active:
        subscriber.is_active = False
        subscriber.save(update_fields=['is_active'])

    return render(
        request,
        'unsubscribe/index.html',
        {'state': 'unsubscribed', 'email': subscriber.email},
    )


def withdraw_application_view(request, token):
    """One-click withdrawal link embedded in the application-received email.

    Same signed-token pattern as unsubscribe_view above — no login
    required, no expiry (a withdrawal link in a two-year-old email should
    still work).
    """
    try:
        application_id = signing.loads(token, salt='application-access')
    except signing.BadSignature:
        return render(
            request,
            'career/withdraw/index.html',
            {'state': 'invalid'},
        )

    application = JobApplication.objects.select_related('job').filter(id=application_id).first()

    if not application:
        return render(
            request,
            'career/withdraw/index.html',
            {'state': 'invalid'},
        )

    if application.status == 'withdrawn':
        return render(
            request,
            'career/withdraw/index.html',
            {'state': 'already_withdrawn', 'job_title': application.job.title},
        )

    application.status = 'withdrawn'
    application.save(update_fields=['status'])

    threading.Thread(
        target=_notify_withdrawal_safely,
        args=(application,),
        daemon=True,
    ).start()

    return render(
        request,
        'career/withdraw/index.html',
        {'state': 'withdrawn', 'job_title': application.job.title},
    )


def _notify_withdrawal_safely(application):
    try:
        _notify_withdrawal(application)
    except Exception:
        logger.exception('Failed to send application withdrawal notification email(s)')


def _notify_withdrawal(application):
    first_name = application.full_name.split(' ')[0] or application.full_name

    body_html = f"""
        <p style="margin:0 0 18px;">Hi {escape(first_name)},</p>
        <p style="margin:0;">
            This confirms your application for <strong>{escape(application.job.title)}</strong>
            at Figbloom Digital Group has been withdrawn. If you didn't request this, contact
            us at <a href="mailto:sales@figbloom.org">sales@figbloom.org</a>.
        </p>
    """

    html_content = build_branded_email_html(
        eyebrow='Application Withdrawn',
        title='Your application has been withdrawn',
        preheader=f'Your application for {application.job.title} was withdrawn',
        body_html=body_html,
    )

    message = EmailMultiAlternatives(
        subject=f'Application withdrawn — {application.job.title}',
        body=(
            f'This confirms your application for {application.job.title} at '
            'Figbloom Digital Group has been withdrawn.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.email],
    )
    message.attach_alternative(html_content, 'text/html')

    logo_image = _load_logo_mime_image()
    if logo_image:
        message.attach(logo_image)

    message.send(fail_silently=False)

    # Quiet internal copy so staff aren't left thinking someone's still in
    # the pipeline when they're not.
    EmailMultiAlternatives(
        subject=f'Applicant withdrew: {application.full_name} — {application.job.title}',
        body=(
            f'{application.full_name} ({application.email}) withdrew their application '
            f'for {application.job.title}.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[CONTACT_NOTIFICATION_RECIPIENT],
    ).send(fail_silently=False)


STATUS_CHANGE_MESSAGES = {
    'new': "Your application has been moved back to New.",
    'reviewed': "Your application is now being reviewed by our team.",
    'shortlisted': "Good news — you've been shortlisted for this role.",
    'interview': "You've been selected for an interview. Our team will be in touch with next steps.",
    'hired': "Congratulations — you've been selected for this role! Our team will reach out with next steps.",
    'withdrawn': "Your application has been marked as withdrawn.",
}


def _notify_status_change_safely(application, withdraw_url):
    try:
        _notify_status_change(application, withdraw_url)
    except Exception:
        logger.exception('Failed to send application status-change notification email')


def _notify_status_change(application, withdraw_url):
    first_name = application.full_name.split(' ')[0] or application.full_name
    status_display = application.get_status_display()

    # Rejection gets its own gentler, fuller wording rather than the plain
    # one-liner every other status uses — it's the one status change that
    # can genuinely sting, so it deserves more care than "Status: Rejected."
    if application.status == 'rejected':
        body_html = f"""
            <p style="margin:0 0 18px;">Hi {escape(first_name)},</p>
            <p style="margin:0 0 18px;">
                Thank you so much for the time and thought you put into applying for the
                <strong>{escape(application.job.title)}</strong> role, and for giving us the
                chance to learn a bit about you.
            </p>
            <p style="margin:0 0 18px;">
                After a lot of careful thought, we've decided to move forward with another
                candidate this time. This really wasn't an easy call, and it isn't a
                reflection of your talent or potential — it often just comes down to fit
                for this specific role, at this specific moment.
            </p>
            <p style="margin:0 0 18px;">
                We'd love to stay in touch. Please don't hesitate to apply again for future
                roles that catch your eye — we'd genuinely welcome hearing from you.
            </p>
            <p style="margin:0;">
                Wishing you all the best, and thank you again for considering Figbloom
                Digital Group.
            </p>
        """
        message = "We've decided to move forward with another candidate for this role."
    else:
        message = STATUS_CHANGE_MESSAGES.get(
            application.status,
            f'Your application status has been updated to {status_display}.',
        )
        body_html = f"""
            <p style="margin:0 0 18px;">Hi {escape(first_name)},</p>
            <p style="margin:0;">
                {escape(message)}
            </p>
        """

    html_content = build_branded_email_html(
        eyebrow='Application Update',
        title=f'Application update — {application.job.title}',
        preheader=f'Your application status is now {status_display}',
        body_html=body_html,
        footer_note_html=(
            "You're receiving this email because you applied for a position at "
            "Figbloom Digital Group."
        ),
        footer_action_html=(
            f'<a href="{withdraw_url}" style="color:#8a978d; text-decoration:underline;">'
            'Withdraw your application</a>'
        ),
    )

    email = EmailMultiAlternatives(
        subject=f'Application update — {application.job.title}: {status_display}',
        body=f'{message} (Status: {status_display})',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.email],
    )
    email.attach_alternative(html_content, 'text/html')

    logo_image = _load_logo_mime_image()
    if logo_image:
        email.attach(logo_image)

    email.send(fail_silently=False)


CONTACT_NOTIFICATION_RECIPIENT = 'sales@figbloom.org'


class ContactCreateView(generics.CreateAPIView):
    queryset = ContactInquiry.objects.all()
    serializer_class = ContactInquirySerializer

    def create(self, request, *args, **kwargs):
        # Honeypot: a genuine visitor never fills this hidden field, so a
        # non-empty value means a bot. Respond as if it succeeded — telling
        # a bot it was rejected just teaches it to try again differently —
        # but skip saving and emailing.
        if request.data.get('website'):
            return Response(
                {'detail': 'Thanks — we\'ll be in touch shortly.'},
                status=status.HTTP_201_CREATED,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inquiry = serializer.save()

        # The inquiry is already saved at this point, so a slow or failing
        # SMTP attempt loses the notification, not the lead — it still shows
        # up for anyone checking the database directly. This runs on a
        # background thread rather than inline: EMAIL_TIMEOUT bounds how
        # long a single send can take, but the visitor shouldn't be stuck on
        # "Sending..." for even that long waiting on a third-party mail
        # server neither of us controls the latency of.
        threading.Thread(target=self._notify_safely, args=(inquiry,), daemon=True).start()

        return Response(
            {
                'detail': 'Thanks — we\'ll be in touch shortly.',
                'inquiry': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def _notify_safely(self, inquiry):
        # Runs on a background thread — an unhandled exception here would
        # only ever surface in the thread's default excepthook, not to the
        # request, so it's caught and logged explicitly instead.
        try:
            self._notify(inquiry)
        except Exception:
            logger.exception('Failed to send contact inquiry notification email')

    def _notify(self, inquiry):
        fields = [
            ('Full name', inquiry.full_name),
            ('Company', inquiry.company),
            ('Email', inquiry.email),
            ('Phone', inquiry.phone),
            ('Interested in', inquiry.service),
            ('Budget', inquiry.budget),
            ('Timeline', inquiry.timeline),
            ('Brief', inquiry.brief),
        ]

        text_lines = [f'{label}: {value}' for label, value in fields if value]
        text_body = '\n'.join(text_lines)

        html_rows = ''.join(
            f'<tr><td style="padding:4px 12px 4px 0;color:#67788f;white-space:nowrap;">{escape(label)}</td>'
            f'<td style="padding:4px 0;">{escape(value).replace(chr(10), "<br>")}</td></tr>'
            for label, value in fields if value
        )
        html_body = f'<table cellpadding="0" cellspacing="0">{html_rows}</table>'

        message = EmailMultiAlternatives(
            subject=f'New contact inquiry from {inquiry.full_name}',
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[CONTACT_NOTIFICATION_RECIPIENT],
            reply_to=[inquiry.email] if inquiry.email else None,
        )
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)


class ContactAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail of contact-form inquiries for the admin dashboard."""
    queryset = ContactInquiry.objects.all().order_by('-created_at')
    serializer_class = ContactInquiryAdminSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]


class DashboardStatsView(APIView):
    """Aggregate counts + a merged recent-activity feed for the dashboard Overview tab."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)

        stats = {
            'open_jobs': Job.objects.open().count(),
            'total_applications': JobApplication.objects.count(),
            'new_applications_7d': JobApplication.objects.filter(applied_at__gte=week_ago).count(),
            'active_subscribers': NewsletterSubscriber.objects.filter(is_active=True).count(),
            'new_subscribers_7d': NewsletterSubscriber.objects.filter(subscribed_at__gte=week_ago).count(),
            'contact_inquiries': ContactInquiry.objects.count(),
            'new_contact_inquiries_7d': ContactInquiry.objects.filter(created_at__gte=week_ago).count(),
        }

        # No natural shared ordering across three unrelated models, so each
        # is pulled independently and merged/sorted here in Python rather
        # than attempted as a single cross-model query.
        recent = []

        for app in JobApplication.objects.select_related('job').order_by('-applied_at')[:8]:
            recent.append({
                'type': 'application',
                'id': app.id,
                'label': f'{app.full_name} applied — {app.job.title}',
                'timestamp': app.applied_at,
                'url': f'/admin-dashboard/application-detail?id={app.id}',
            })

        for inquiry in ContactInquiry.objects.order_by('-created_at')[:8]:
            recent.append({
                'type': 'contact',
                'id': inquiry.id,
                'label': f'New contact inquiry from {inquiry.full_name}',
                'timestamp': inquiry.created_at,
                'url': '/admin-dashboard/contact',
            })

        for sub in NewsletterSubscriber.objects.order_by('-subscribed_at')[:8]:
            recent.append({
                'type': 'subscriber',
                'id': sub.id,
                'label': f'New subscriber — {sub.email}',
                'timestamp': sub.subscribed_at,
                'url': '/admin-dashboard/subscribers',
            })

        recent.sort(key=lambda item: item['timestamp'], reverse=True)

        return Response({
            'stats': stats,
            'recent_activity': recent[:10],
        })

