from django.conf import settings
from django.db import models


def project_image_storage():
    # Photos should be served as images (not Cloudinary's "raw" type, which is
    # the default storage here and is right for CVs) so they display and cache
    # like normal images. Same reasoning as the newsletter and activity covers.
    if settings.USE_CLOUDINARY:
        from cloudinary_storage.storage import MediaCloudinaryStorage

        return MediaCloudinaryStorage()

    from django.core.files.storage import default_storage

    return default_storage


class ProjectQuerySet(models.QuerySet):
    def published(self):
        """What visitors can see. Unpublished projects stay in the dashboard."""
        return self.filter(is_published=True)

    def on_home(self):
        return self.published().filter(show_on_home=True)


class Project(models.Model):
    objects = ProjectQuerySet.as_manager()

    title = models.CharField(max_length=200)
    # Free text rather than a fixed list: the portfolio's categories are the
    # company's to define. The serializer reuses an existing spelling when only
    # the capitalisation differs, so "branding" can't spawn a second tab.
    category = models.CharField(max_length=80)
    description = models.CharField(max_length=500)
    # The small badge on the card, e.g. "+42% conversion".
    highlight = models.CharField(max_length=80, blank=True)
    # Optional case study / live site. Without it the card isn't clickable.
    link_url = models.URLField(max_length=500, blank=True)
    image = models.ImageField(
        upload_to='projects/',
        storage=project_image_storage,
        blank=True,
        null=True,
    )
    # An image that already lives on the site itself (for example
    # /assets/images/project-1.jpg), used until someone uploads their own.
    # Only the seed migration sets it; the dashboard can't edit it.
    static_image = models.CharField(max_length=300, blank=True, editable=False)
    is_published = models.BooleanField(default=True)
    show_on_home = models.BooleanField(default=True)
    # Lower comes first. New projects start at 0, which puts them at the top
    # (newest first among equals); the dashboard's move up / down buttons
    # renumber everything from 1.
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at', '-id']

    @property
    def image_src(self):
        """The address of the picture to show, uploaded or built-in."""
        if self.image:
            return self.image.url

        return self.static_image

    def __str__(self):
        return self.title
