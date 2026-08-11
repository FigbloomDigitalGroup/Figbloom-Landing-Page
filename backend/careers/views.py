from django.shortcuts import get_object_or_404, render, redirect
from rest_framework import generics, status
from rest_framework.response import Response
from .models import Job, JobApplication, NewsletterSubscriber
from .serializers import JobSerializer, JobApplicationSerializer, NewsletterSubscriberSerializer
from django.contrib import messages
from .forms import JobApplicationForm


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