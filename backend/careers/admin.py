from django.contrib import admin
from .models import Job, JobApplication, NewsletterSubscriber


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'department',
        'location',
        'employment_type',
        'deadline',
        'is_open',
    )

    list_filter = (
        'is_open',
        'employment_type',
        'department',
        'location',
    )

    search_fields = (
        'title',
        'department',
        'location',
    )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'job_title',
        'email',
        'phone',
        'status',
        'applied_at',
    )

    list_filter = (
        'status',
        'job',
    )

    search_fields = (
        'full_name',
        'email',
        'phone',
        'job__title',
    )

    def job_title(self, obj):
        return obj.job.title

    job_title.short_description = 'Job'


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "subscribed_at", "is_active")
    list_filter = ("is_active", "subscribed_at")
    search_fields = ("email",)
    ordering = ("-subscribed_at",)    