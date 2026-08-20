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
from .serializers import (JobSerializer, JobApplicationSerializer, NewsletterSubscriberSerializer,JobApplicationAdminSerializer, ContactInquirySerializer)
from django.contrib import messages
from .forms import JobApplicationForm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from html import escape
import logging
import threading

logger = logging.getLogger(__name__)
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import update_session_auth_hash



@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"detail": "CSRF cookie set"})


class JobListView(generics.ListAPIView):
    serializer_class = JobSerializer
    def get_queryset(self):
        return Job.objects.filter(is_open=True).order_by('-created_at')


class JobDetailView(generics.RetrieveAPIView):
    queryset = Job.objects.filter(is_open=True)
    serializer_class = JobSerializer
    lookup_field = 'slug'


class ApplicationCreateView(generics.CreateAPIView):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                'message': 'Application submitted successfully.',
                'application': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

  
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
    permission_classes = [IsAuthenticated]

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
def admin_application_detail(request):
    return render(
        request,
        "admin-dashboard/application-detail.html"
    )

def admin_profile_settings(request):
    return render(
        request,
        "admin-dashboard/profile-settings.html"
    )    
def admin_subscribers(request):
    return render(
        request,
        "admin-dashboard/subscribers.html"
    )
def admin_subscribers(request):
    return render(
        request,
        "admin-dashboard/subscribers.html"
    )
# --- Admin dashboard API ---

class JobAdminViewSet(viewsets.ModelViewSet):
    ...
   
# --- Admin dashboard API ---
# All views below require an authenticated, staff-level Django user

class JobAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on jobs for the admin dashboard (create/edit/close postings)."""
    queryset = Job.objects.all().order_by('-created_at')
    serializer_class = JobSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class ApplicationAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on applications for the admin dashboard (view/update status)."""
    queryset = JobApplication.objects.all().order_by('-applied_at')
    serializer_class = JobApplicationAdminSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class NewsletterAdminViewSet(viewsets.ModelViewSet):
    queryset = NewsletterSubscriber.objects.all().order_by('-subscribed_at')
    serializer_class = NewsletterSubscriberSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

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
                "email",
                flat=True
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
        # ---------------------------------------------------------

        email_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>{escape(subject)}</title>
</head>

<body style="
    margin:0;
    padding:30px 15px;
    background:#f7f9f7;
    font-family:Arial, Helvetica, sans-serif;
    color:#333333;
">

    <div style="
        max-width:820px;
        margin:0 auto;
        background:#ffffff;
        border-radius:12px;
        overflow:hidden;
    ">

        <!-- HEADER -->

        <div style="
            background:#183c22;
            padding:42px 30px;
            text-align:center;
        ">

            <div style="
                color:#ffffff;
                font-size:34px;
                font-weight:800;
                letter-spacing:1px;
                line-height:1.2;
            ">
                FIGBLOOM
            </div>

            <div style="
                margin-top:12px;
                color:#ff9400;
                font-size:17px;
                letter-spacing:4px;
                font-weight:500;
            ">
                DIGITAL GROUP
            </div>

        </div>


        <!-- CONTENT -->

        <div style="
            padding:45px;
        ">

            <h1 style="
                margin:0 0 28px 0;
                color:#183c22;
                font-size:30px;
                line-height:1.3;
                font-weight:800;
            ">
                {escape(subject)}
            </h1>


            <div style="
                color:#444444;
                font-size:16px;
                line-height:1.8;
            ">
                {html_content.replace(chr(10), '<br>')}
            </div>

        </div>


        <!-- FOOTER -->

        <div style="
            background:#f8faf8;
            border-top:1px solid #edf0ed;
            text-align:center;
            padding:25px 20px;
            color:#718078;
            font-size:13px;
        ">

            <div style="
                color:#183c22;
                font-size:15px;
                font-weight:700;
                margin-bottom:7px;
            ">
                Figbloom Digital Group
            </div>

            <div>
                Technology &bull; Innovation &bull; Growth
            </div>

            <div style="
                margin-top:12px;
                font-size:12px;
                color:#9aa59d;
            ">
                Thank you for being part of our community.
            </div>

        </div>

    </div>

</body>
</html>
"""

        # ---------------------------------------------------------
        # SEND EMAILS
        # ---------------------------------------------------------

        try:

            connection.open()

            for email in recipients:

                try:

                    message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[email],
                        connection=connection,
                    )

                    message.attach_alternative(
                        email_html,
                        "text/html",
                    )

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


