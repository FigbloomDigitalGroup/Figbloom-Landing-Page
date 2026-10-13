from rest_framework import serializers
from .models import Job, JobApplication, NewsletterSubscriber, SentNewsletter, ContactInquiry


class JobSerializer(serializers.ModelSerializer):
    is_currently_open = serializers.BooleanField(read_only=True)

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
            'is_currently_open',
            'created_at',
        ]


class JobApplicationSerializer(serializers.ModelSerializer):
    job = serializers.PrimaryKeyRelatedField(queryset=Job.objects.open())

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
        fields = ["id", "email", "is_active", "is_suspended", "suspended_at", "subscribed_at"]
        # Suspension only changes through the admin suspend/unsuspend actions.
        read_only_fields = ["id", "is_suspended", "suspended_at", "subscribed_at"]


class SentNewsletterSerializer(serializers.ModelSerializer):
    sent_by = serializers.CharField(source="sent_by.username", default="", read_only=True)

    class Meta:
        model = SentNewsletter
        fields = [
            "id",
            "subject",
            "content",
            "audience",
            "total_recipients",
            "sent_count",
            "failed_count",
            "failed_emails",
            "sent_by",
            "sent_at",
        ]
        read_only_fields = fields


class ContactInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInquiry
        fields = [
            'id',
            'full_name',
            'company',
            'email',
            'phone',
            'service',
            'budget',
            'timeline',
            'brief',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# --- Admin-facing serializers ---
# Used by the protected /api/admin/... endpoints. Unlike the public
# serializers above, these expose all fields (including status) and are
# writable, since only authenticated staff can reach these views.

class JobApplicationAdminSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)

    class Meta:
        model = JobApplication
        fields = '__all__'


class ContactInquiryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInquiry
        fields = '__all__'