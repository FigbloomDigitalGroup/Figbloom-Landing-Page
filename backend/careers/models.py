from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


def newsletter_cover_storage():
    # The default Cloudinary storage is the "raw" one (fine for CVs), but
    # cover images should be served as images so link previews pick them up.
    if settings.USE_CLOUDINARY:
        from cloudinary_storage.storage import MediaCloudinaryStorage

        return MediaCloudinaryStorage()

    from django.core.files.storage import default_storage

    return default_storage

# Create your models here.


class JobQuerySet(models.QuerySet):
    def open(self):
        """Jobs actually visible/applicable-to on the public site: staff
        hasn't closed them AND (no deadline, or the deadline hasn't passed
        yet). A passed deadline auto-closes a job the same way manually
        flipping is_open does, without ever touching the stored is_open
        value — so extending the deadline later doesn't require a staff
        member to remember to re-open it."""
        return self.filter(is_open=True).filter(
            Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate())
        )


class Job(models.Model):
    WORK_ARRANGEMENT_CHOICES = [
        ('onsite', 'Onsite'),
        ('hybrid', 'Hybrid'),
        ('remote', 'Remote'),
    ]

    objects = JobQuerySet.as_manager()

    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    slug = models.SlugField(max_length=200, blank=True)
    location = models.CharField(
        max_length=20,
        choices=WORK_ARRANGEMENT_CHOICES,
        default='onsite',
    )

    employment_type = models.CharField(
        max_length=60,
        choices=[
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
            ('contract', 'Contract'),
            ('internship', 'Internship'),
        ]
    )

    experience = models.CharField(max_length=100, blank=True)
    salary = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    requirements = models.TextField()
    deadline = models.DateField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug or 'job'
            counter = 1

            while Job.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def is_currently_open(self):
        return self.is_open and (self.deadline is None or self.deadline >= timezone.localdate())

    def __str__(self):
        return self.title

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
        ('withdrawn', 'Withdrawn'),
    ]

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    portfolio = models.URLField(max_length=500, blank=True, default='')
    cover_letter = models.TextField(blank=True)
    cv_file = models.FileField(upload_to='cv/', blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )

    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'email'],
                name='unique_application_per_job_email',
            ),
        ]

    def save(self, *args, **kwargs):
        # Normalized so the (job, email) uniqueness check/constraint treats
        # Foo@Bar.com and foo@bar.com as the same applicant.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.job.title}"


Application = JobApplication


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # Staff-imposed block, kept separate from is_active (which the
    # subscriber controls via subscribe/unsubscribe) so re-subscribing
    # from the public form can't lift a suspension.
    is_suspended = models.BooleanField(default=False)
    suspended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email


class SentNewsletter(models.Model):
    """A record of each newsletter sent, for the dashboard's history."""

    subject = models.CharField(max_length=200)
    # Public web address: /newsletters/<slug>/. Set once from the subject
    # and never changed, so links already shared keep working.
    slug = models.SlugField(max_length=220, unique=True, null=True, blank=True)
    content = models.TextField()
    # Optional image shown on top of the email and public page, and used
    # as the link-preview image when the page is shared.
    cover_image = models.ImageField(
        upload_to='newsletters/',
        storage=newsletter_cover_storage,
        width_field='cover_width',
        height_field='cover_height',
        blank=True,
        null=True,
    )
    cover_width = models.PositiveIntegerField(null=True, blank=True)
    cover_height = models.PositiveIntegerField(null=True, blank=True)
    # Who it went to: "all" active subscribers or "selected" ones.
    audience = models.CharField(max_length=50, blank=True, default='all')
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    failed_emails = models.JSONField(default=list, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_newsletter_slug(SentNewsletter, self.subject, exclude_pk=self.pk)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f'/newsletters/{self.slug}/'

    def __str__(self):
        return self.subject


def unique_newsletter_slug(model, subject, exclude_pk=None):
    """Slug from the subject, with -2, -3… added if it's already taken.
    Takes the model class so the data migration can reuse it."""
    base_slug = slugify(subject)[:200] or 'newsletter'
    slug = base_slug
    counter = 2

    while model.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    return slug


class ContactInquiry(models.Model):
    full_name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default='')
    service = models.CharField(max_length=100, blank=True, default='')
    budget = models.CharField(max_length=100, blank=True, default='')
    timeline = models.CharField(max_length=100, blank=True, default='')
    brief = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.email}"

    