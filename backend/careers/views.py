from django.shortcuts import get_object_or_404, render, redirect
from rest_framework import generics, status, viewsets, permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.decorators import APIView, action
from .models import Job, JobApplication, NewsletterSubscriber
from .serializers import (JobSerializer, JobApplicationSerializer, NewsletterSubscriberSerializer,JobApplicationAdminSerializer)
from django.contrib import messages
from .forms import JobApplicationForm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated



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

class NewsletterSubscribeView(generics.CreateAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"error": "Email address is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if NewsletterSubscriber.objects.filter(email=email).exists():
            return Response(
                {"message": "This email is already subscribed."},
                status=status.HTTP_200_OK
            )

        NewsletterSubscriber.objects.create(email=email)

        return Response(
            {"message": "Successfully subscribed to the newsletter!"},
            status=status.HTTP_201_CREATED
        )
        


def job_detail(request, slug):
    job = get_object_or_404(Job, slug=slug, is_open=True)
    return render(request, "career/job_detail.html", {"job": job})

def apply_for_job(request, slug):
    job = get_object_or_404(Job, slug=slug, is_open=True)

    if request.method == "POST":
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.save()
            messages.success(request, "Your application was submitted successfully.")
            return redirect("job_detail", slug=job.slug)
    else:
        form = JobApplicationForm()

    return render(request, "career/apply.html", {"job": job, "form": form})


def admin_application_detail(request):
    return render(
        request,
        'admin-dashboard/application-detail.html'
    )
  

   
# --- Admin dashboard API ---
# All views below require an authenticated, staff-level Django user
# (session cookie based, since the admin dashboard is served by this
# same Django app). Public visitors never reach these.

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


class NewsletterAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of newsletter subscribers for the admin dashboard."""
    queryset = NewsletterSubscriber.objects.all().order_by('-subscribed_at')
    serializer_class = NewsletterSubscriberSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a newsletter to active subscribers.

        Expected JSON: { subject, body, html (optional), limit (optional), test_email (optional), dry_run (optional) }
        """
        from .utils import send_newsletter

        if not request.user or not request.user.is_authenticated or not request.user.is_staff:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        subject = request.data.get('subject', '').strip()
        body = request.data.get('body', '').strip()
        html = request.data.get('html')
        limit = request.data.get('limit')
        test_email = request.data.get('test_email')
        dry_run = bool(request.data.get('dry_run', False))

        if not subject:
            return Response({'detail': 'Subject is required.'}, status=status.HTTP_400_BAD_REQUEST)

        recipients = [test_email] if test_email else None

        sent = send_newsletter(subject=subject, text_body=body or '', html_body=html, recipients=recipients, limit=limit, dry_run=dry_run)

        return Response({'detail': 'Newsletter processed.', 'recipients': sent, 'count': len(sent)})
    
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



class NewsletterSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subject = request.data.get("subject", "").strip()
        content = request.data.get("content", "").strip()

        if not subject:
            return Response(
                {"detail": "Newsletter subject is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not content:
            return Response(
                {"detail": "Newsletter content is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscribers = NewsletterSubscriber.objects.filter(
            is_active=True
        )

        total = subscribers.count()

        if total == 0:
            return Response(
                {
                    "success": False,
                    "detail": "There are no active newsletter subscribers.",
                    "sent": 0,
                    "failed": 0,
                    "total": 0,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        sent = 0
        failed = 0
        failed_emails = []

        for subscriber in subscribers:

            try:
                text_content = (
                    "Hello,\n\n"
                    "Here is the latest update from Figbloom Digital Group.\n\n"
                    + content
                    + "\n\n"
                    "Thank you for being part of the Figbloom community."
                )

                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport"
                          content="width=device-width, initial-scale=1.0">
                </head>

                <body style="
                    margin:0;
                    padding:0;
                    background:#f5f7f5;
                    font-family:Arial,Helvetica,sans-serif;
                ">

                    <div style="
                        max-width:680px;
                        margin:40px auto;
                        background:#ffffff;
                        border-radius:16px;
                        overflow:hidden;
                        box-shadow:0 8px 30px rgba(0,0,0,0.08);
                    ">

                        <div style="
                            background:#1a3a1a;
                            padding:30px;
                            text-align:center;
                        ">
                            <img
                                src="https://www.figbloom.org/assets/images/figbloom_logo.png"
                                alt="Figbloom Digital Group"
                                style="
                                    width:120px;
                                    max-width:100%;
                                "
                            >
                        </div>

                        <div style="padding:40px 35px;">

                            <h1 style="
                                margin:0 0 25px;
                                color:#1a3a1a;
                                font-size:28px;
                            ">
                                {subject}
                            </h1>

                            <div style="
                                color:#444444;
                                font-size:16px;
                                line-height:1.7;
                            ">
                                {content}
                            </div>

                        </div>

                        <div style="
                            background:#f7f8f7;
                            padding:25px 35px;
                            text-align:center;
                            color:#777777;
                            font-size:13px;
                        ">

                            <p style="margin:0 0 8px;">
                                Figbloom Digital Group
                            </p>

                            <p style="margin:0;">
                                Thank you for being part of our community.
                            </p>

                        </div>

                    </div>

                </body>
                </html>
                """

                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[subscriber.email],
                )

                email.attach_alternative(
                    html_content,
                    "text/html"
                )

                email.send(fail_silently=False)

                sent += 1

            except Exception as error:
                failed += 1
                failed_emails.append({
                    "email": subscriber.email,
                    "error": str(error),
                })

        return Response(
            {
                "success": failed == 0,
                "detail": (
                    f"Newsletter processed. "
                    f"{sent} sent, {failed} failed."
                ),
                "sent": sent,
                "failed": failed,
                "total": total,
                "failed_emails": failed_emails,
            },
            status=status.HTTP_200_OK
        )