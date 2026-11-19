import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser

from .categories import CATEGORIES
from .models import Activity
from .serializers import ActivityAdminSerializer, delete_stored_file

SITE_URL = 'https://figbloom.org'
RELATED_COUNT = 3

# The three photos in the hero collage. They are fixed site images, not activity
# covers: adding an activity, or editing or replacing its cover in the
# dashboard, never changes the hero. To change the hero, edit this list.
HERO_PHOTOS = [
    '/assets/images/gallery1.jpg',
    '/assets/images/gallery7.jpg',
    '/assets/images/teams9.jpeg',
]

# The strip of shortcuts under the hero. Each one filters the list below to a
# category that has a tab (see categories.py).
HIGHLIGHTS = [
    {'key': 'update', 'title': 'Stories', 'blurb': 'Read inspiring stories', 'icon': 'megaphone'},
    {'key': 'event', 'title': 'Events', 'blurb': 'Discover upcoming events', 'icon': 'calendar-days'},
    {'key': 'community', 'title': 'Community', 'blurb': 'See our community impact', 'icon': 'users'},
    {'key': 'achievement', 'title': 'Impact', 'blurb': 'Celebrating achievements', 'icon': 'trophy'},
]


def _absolute(url):
    """An address usable in og:image / JSON-LD. Cloudinary already returns a
    full URL; local-disk media is a path on this site."""
    if not url:
        return ''

    return url if url.startswith(('http://', 'https://')) else f'{SITE_URL}{url}'


def _json_ld(data):
    """JSON for an inline <script type="application/ld+json"> block. `<` is
    escaped so a title containing "</script>" can't end the block early."""
    return json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')


# --- Public pages -------------------------------------------------------

def activities_page(request):
    activities = list(Activity.objects.published())

    counts = {}
    for activity in activities:
        counts[activity.category] = counts.get(activity.category, 0) + 1

    # Only categories that have a tab AND something to show get a filter chip —
    # a row of dead chips on a young site just reads as broken. Entries in a
    # category without a tab are still listed under "All Activities".
    categories = [
        {**category, 'count': counts[category['key']]}
        for category in CATEGORIES
        if category['tab'] and counts.get(category['key'])
    ]

    # Only the link-preview picture (og:image) follows the newest cover. The hero
    # collage does not: it always shows HERO_PHOTOS.
    first_with_photo = next((a for a in activities if a.cover_image), None)

    return render(request, 'activities/index.html', {
        'activities': activities,
        'categories': categories,
        'highlights': HIGHLIGHTS,
        'hero_images': HERO_PHOTOS,
        'total': len(activities),
        'og_image': _absolute(first_with_photo.cover_image.url) if first_with_photo else '',
    })


def activity_detail_page(request, slug):
    # Staff can open a draft by its link to preview it before publishing.
    queryset = Activity.objects.all() if request.user.is_staff else Activity.objects.published()
    activity = get_object_or_404(queryset, slug=slug)

    related = list(
        Activity.objects.published()
        .filter(category=activity.category)
        .exclude(pk=activity.pk)[:RELATED_COUNT]
    )

    # A small category shouldn't leave the "keep reading" row bare — top it up
    # with the latest from elsewhere.
    if len(related) < RELATED_COUNT:
        taken = [activity.pk] + [a.pk for a in related]
        related += list(
            Activity.objects.published().exclude(pk__in=taken)[:RELATED_COUNT - len(related)]
        )

    canonical_url = f'{SITE_URL}{activity.get_absolute_url()}'
    og_image = _absolute(activity.cover_image.url) if activity.cover_image else ''
    publisher = {
        '@type': 'Organization',
        'name': 'Figbloom Digital Group',
        'logo': {'@type': 'ImageObject', 'url': f'{SITE_URL}/assets/images/figbloom_logo.png'},
    }

    article = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': activity.title,
        'description': activity.summary,
        'datePublished': activity.activity_date.isoformat(),
        'dateModified': activity.updated_at.date().isoformat(),
        'mainEntityOfPage': canonical_url,
        'author': publisher,
        'publisher': publisher,
    }
    if og_image:
        article['image'] = [og_image]

    breadcrumbs = {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{SITE_URL}/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Activities', 'item': f'{SITE_URL}/activities/'},
            {'@type': 'ListItem', 'position': 3, 'name': activity.title, 'item': canonical_url},
        ],
    }

    return render(request, 'activities/detail.html', {
        'activity': activity,
        'related': related,
        'canonical_url': canonical_url,
        'og_image': og_image,
        'json_ld': _json_ld([article, breadcrumbs]),
    })


# --- Admin dashboard ----------------------------------------------------

@login_required(login_url='/admin-dashboard/login')
def admin_activities_page(request):
    return render(request, 'admin-dashboard/activities.html', {
        'active_nav': 'activities',
        'categories': CATEGORIES,
    })


class ActivityAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on activities for the dashboard, including cover-image upload
    (multipart) and the publish / feature switches."""
    queryset = Activity.objects.all()
    serializer_class = ActivityAdminSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # The dashboard filters and searches client-side over the full list, same
    # as the jobs table, so no pagination.
    pagination_class = None

    def perform_destroy(self, instance):
        image = instance.cover_image
        name = image.name if image else None
        storage = image.storage if image else None

        instance.delete()
        delete_stored_file(storage, name)
