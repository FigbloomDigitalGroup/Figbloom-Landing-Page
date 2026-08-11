from rest_framework import serializers
from .models import Job, JobApplication, NewsletterSubscriber


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            'id',
            'slug',
            'title',
            'department',
            'location',
            'employment_type',
            'experience',
            'salary',
            'description',
            'requirements',
            'deadline',
            'is_open',
            'created_at',
        ]


class JobApplicationSerializer(serializers.ModelSerializer):
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.filter(is_open=True))

    class Meta:
        model = JobApplication
        fields = [
            'id',
            'job',
            'full_name',
            'email',
            'phone',
            'portfolio',
            'cover_letter',
            'cv_file',
            'status',
            'applied_at',
        ]
        read_only_fields = [
            'status',
            'applied_at',
        ]


ApplicationSerializer = JobApplicationSerializer


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ["id", "email", "subscribed_at"]
        read_only_fields = ["id", "subscribed_at"]       