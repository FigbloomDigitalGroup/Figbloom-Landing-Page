from django.db import models
from django.utils.text import slugify

# Create your models here.


class Job(models.Model):
    WORK_ARRANGEMENT_CHOICES = [
        ('onsite', 'Onsite'),
        ('hybrid', 'Hybrid'),
        ('remote', 'Remote'),
    ]

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

    def __str__(self):
        return f"{self.full_name} - {self.job.title}"


Application = JobApplication


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


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

    