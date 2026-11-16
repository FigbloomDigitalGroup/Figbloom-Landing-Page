from django.db import migrations

# The six projects that used to be typed straight into frontend/projects/index.html,
# carried over unchanged (apart from a stray trailing space in the first title) so
# the public page looks the same the day this ships. After that they are ordinary
# rows, edited from the dashboard like any other.
#
# static_image points at the picture already on the site; it is used until
# someone uploads a replacement.
EXISTING_PROJECTS = [
    {
        'title': 'Movecconnect',
        'description': (
            'MovecConnect provides reliable Starlink-powered internet solutions, connecting '
            'homes and businesses with fast, affordable, and dependable broadband access'
        ),
        'static_image': '/assets/images/project-1.jpg',
        'category': 'Web Development',
        'highlight': '+42% conversion',
    },
    {
        'title': 'Figbloom Ecommerce App',
        'description': (
            'Figbloom E-commerce supplies Starlink kits, security cameras, networking '
            'equipment, and smart technology solutions for homes and businesses.'
        ),
        'static_image': '/assets/images/project-2.jpg',
        'category': 'Web App Development',
        'highlight': '−38% user drop-off',
    },
    {
        'title': 'Figbloom Brand Identity',
        'description': 'A modern visual identity crafted to reflect trust and innovation.',
        'static_image': '/assets/images/project-3.jpg',
        'category': 'Branding',
        'highlight': '2× brand recall',
    },
    {
        'title': 'GrowFast Campaign',
        'description': 'A performance-driven digital campaign optimized for qualified leads.',
        'static_image': '/assets/images/project-4.jpg',
        'category': 'Digital Marketing',
        'highlight': '+61% lead growth',
    },
    {
        'title': 'Pulse SaaS Product',
        'description': 'An end-to-end SaaS product designed and developed from idea to launch.',
        'static_image': '/assets/images/project-5.jpg',
        'category': 'Product Development',
        'highlight': 'Launched in 90 days',
    },
    {
        'title': 'SSa Flight Automation System',
        'description': 'Automated internal workflows to eliminate manual processes and delays.',
        'static_image': '/assets/images/project-3.jpg',
        'category': 'Automation',
        'highlight': '−55% operational time',
    },
]


def seed_projects(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')

    # Never touch a table that already has content (for instance if this runs
    # again after projects were added by hand).
    if Project.objects.exists():
        return

    Project.objects.bulk_create([
        Project(sort_order=position, is_published=True, show_on_home=True, **fields)
        for position, fields in enumerate(EXISTING_PROJECTS, start=1)
    ])


def unseed_projects(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')

    # Only the untouched originals: still on their built-in picture.
    Project.objects.filter(
        title__in=[fields['title'] for fields in EXISTING_PROJECTS],
        static_image__startswith='/assets/images/project-',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_projects, unseed_projects),
    ]
