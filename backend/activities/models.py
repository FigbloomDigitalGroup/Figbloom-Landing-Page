import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .categories import CATEGORY_BY_KEY, CATEGORY_CHOICES


def activity_image_storage():
    # Same reasoning as the newsletter covers: the default Cloudinary storage
    # is the "raw" one (right for CVs), but photos should be served as images
    # so link previews and responsive delivery work.
    if settings.USE_CLOUDINARY:
        from cloudinary_storage.storage import MediaCloudinaryStorage

        return MediaCloudinaryStorage()

    from django.core.files.storage import default_storage

    return default_storage


class ActivityQuerySet(models.QuerySet):
    def published(self):
        """What visitors can see. Drafts stay in the dashboard only."""
        return self.filter(is_published=True)


class Activity(models.Model):
    objects = ActivityQuerySet.as_manager()

    title = models.CharField(max_length=200)
    # Public address: /activities/<slug>/. Set once from the title and never
    # changed afterwards, so a link that was already shared keeps working
    # even if the title is later corrected.
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='event',
        db_index=True,
    )
    # The short text on the card, and the link-preview description.
    summary = models.CharField(max_length=280)
    # The full story shown on the detail page. Plain text — a blank line
    # starts a new paragraph. (Deliberately not HTML: nothing staff type can
    # inject markup into a public page.)
    content = models.TextField(blank=True)
    activity_date = models.DateField(default=timezone.localdate)
    location = models.CharField(max_length=120, blank=True)
    cover_image = models.ImageField(
        upload_to='activities/',
        storage=activity_image_storage,
        blank=True,
        null=True,
    )
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        verbose_name_plural = 'activities'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_activity_slug(self.title, exclude_pk=self.pk)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f'/activities/{self.slug}/'

    @property
    def category_info(self):
        return CATEGORY_BY_KEY.get(self.category, CATEGORY_BY_KEY['event'])

    @property
    def category_label(self):
        return self.category_info['label']

    @property
    def paragraphs(self):
        """The content split on blank lines, for the detail page."""
        return [p.strip() for p in re.split(r'\n\s*\n', self.content or '') if p.strip()]

    def __str__(self):
        return self.title


def unique_activity_slug(title, exclude_pk=None):
    """Slug from the title, with -2, -3… added if it's already taken."""
    base_slug = slugify(title)[:200] or 'activity'
    slug = base_slug
    counter = 2

    while Activity.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    return slug
