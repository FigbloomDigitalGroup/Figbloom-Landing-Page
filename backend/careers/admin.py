from django.contrib import admin
from .models import Job, JobApplication, NewsletterSubscriber, SentNewsletter, ContactInquiry


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
    list_display = ("email", "subscribed_at", "is_active", "is_suspended")
    list_filter = ("is_active", "is_suspended", "subscribed_at")
    search_fields = ("email",)
    ordering = ("-subscribed_at",)


@admin.register(SentNewsletter)
class SentNewsletterAdmin(admin.ModelAdmin):
    list_display = ("subject", "sent_at", "audience", "sent_count", "failed_count", "sent_by")
    search_fields = ("subject",)
    ordering = ("-sent_at",)
    readonly_fields = [f.name for f in SentNewsletter._meta.fields]


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'company',
        'email',
        'phone',
        'service',
        'created_at',
    )

    list_filter = (
        'service',
        'budget',
        'timeline',
    )

    search_fields = (
        'full_name',
        'company',
        'email',
        'phone',
    )

    ordering = ('-created_at',)    