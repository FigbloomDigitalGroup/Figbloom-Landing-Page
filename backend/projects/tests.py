import importlib
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from .models import Project

User = get_user_model()

API_URL = '/api/admin/projects/'


def make_image(name='shot.png', size=(40, 30)):
    buffer = BytesIO()
    Image.new('RGB', size, (44, 83, 34)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def make_project(**overrides):
    fields = {
        'title': 'Acme Portal',
        'category': 'Web Development',
        'description': 'A portal for Acme.',
    }
    fields.update(overrides)
    return Project.objects.create(**fields)


class EmptyTableTestCase(TestCase):
    """The seed migration fills the table with the site's original projects.
    Tests about listings and ordering want to start from nothing."""

    def setUp(self):
        Project.objects.all().delete()


class SeedMigrationTests(TestCase):
    """The original hardcoded projects must survive the move to the database."""

    def test_the_six_original_projects_are_seeded_in_order(self):
        titles = list(Project.objects.values_list('title', flat=True))

        self.assertEqual(titles, [
            'Movecconnect',
            'Figbloom Ecommerce App',
            'Figbloom Brand Identity',
            'GrowFast Campaign',
            'Pulse SaaS Product',
            'SSa Flight Automation System',
        ])

    def test_seeded_projects_keep_their_pictures_categories_and_badges(self):
        by_title = {p.title: p for p in Project.objects.all()}

        first = by_title['Movecconnect']
        self.assertEqual(first.image_src, '/assets/images/project-1.jpg')
        self.assertEqual(first.category, 'Web Development')
        self.assertEqual(first.highlight, '+42% conversion')
        self.assertEqual(by_title['Figbloom Ecommerce App'].highlight, '−38% user drop-off')
        self.assertEqual(by_title['Figbloom Brand Identity'].highlight, '2× brand recall')

    def test_seeded_projects_are_visible_and_have_no_link(self):
        for project in Project.objects.all():
            self.assertTrue(project.is_published)
            self.assertTrue(project.show_on_home)
            self.assertEqual(project.link_url, '')

    def test_seeding_again_leaves_existing_projects_alone(self):
        module = importlib.import_module('projects.migrations.0002_seed_existing_projects')
        Project.objects.filter(title='Pulse SaaS Product').update(title='Edited by hand')

        module.seed_projects(apps, None)

        self.assertEqual(Project.objects.count(), 6)
        self.assertTrue(Project.objects.filter(title='Edited by hand').exists())

    def test_reversing_removes_only_the_untouched_originals(self):
        module = importlib.import_module('projects.migrations.0002_seed_existing_projects')
        # One original that has since been given its own upload, one new project.
        Project.objects.filter(title='GrowFast Campaign').update(static_image='')
        make_project(title='Added later')

        module.unseed_projects(apps, None)

        self.assertEqual(
            set(Project.objects.values_list('title', flat=True)),
            {'GrowFast Campaign', 'Added later'},
        )


class ProjectModelTests(EmptyTableTestCase):
    def test_published_excludes_hidden_projects(self):
        live = make_project(title='Live')
        make_project(title='Hidden', is_published=False)

        self.assertEqual(list(Project.objects.published()), [live])

    def test_on_home_needs_both_published_and_the_homepage_flag(self):
        shown = make_project(title='Shown')
        make_project(title='Not on home', show_on_home=False)
        make_project(title='Hidden', is_published=False)

        self.assertEqual(list(Project.objects.on_home()), [shown])

    def test_ordered_by_sort_order_then_newest_first(self):
        first = make_project(title='First', sort_order=1)
        second = make_project(title='Second', sort_order=2)
        newer_unsorted = make_project(title='Newer, never sorted')
        older_unsorted = Project.objects.create(
            title='Older, never sorted', category='x', description='x'
        )
        Project.objects.filter(pk=older_unsorted.pk).update(created_at='2020-01-01T00:00:00Z')

        self.assertEqual(
            list(Project.objects.all()),
            [newer_unsorted, older_unsorted, first, second],
        )

    def test_image_src_prefers_an_upload_over_the_built_in_picture(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            project = make_project(static_image='/assets/images/project-1.jpg')
            self.assertEqual(project.image_src, '/assets/images/project-1.jpg')

            project.image.save('mine.png', make_image(), save=True)
            self.assertIn('/media/projects/', project.image_src)

    def test_image_src_is_empty_without_any_picture(self):
        self.assertEqual(make_project().image_src, '')


class PublicPageTests(EmptyTableTestCase):
    def test_projects_page_lists_only_published_projects(self):
        make_project(title='Visible one')
        make_project(title='Secret one', is_published=False)

        response = self.client.get('/projects/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible one')
        self.assertNotContains(response, 'Secret one')

    def test_projects_page_has_a_tab_per_category_in_order_of_appearance(self):
        make_project(title='A', category='Branding', sort_order=1)
        make_project(title='B', category='Automation', sort_order=2)
        make_project(title='C', category='Branding', sort_order=3)

        response = self.client.get('/projects/')

        self.assertEqual(response.context['project_categories'], ['Branding', 'Automation'])
        self.assertContains(response, 'data-tab="Branding"', count=1)
        self.assertContains(response, 'data-tab="Automation"', count=1)

    def test_projects_page_empty_state(self):
        response = self.client.get('/projects/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Projects are on the way')
        # (the page's script always mentions data-project; a card has data-category="...")
        self.assertNotContains(response, 'data-category="')

    def test_a_card_is_only_clickable_when_it_has_a_link(self):
        make_project(title='No link here')
        make_project(title='Has a link', link_url='https://example.com/case-study')

        body = self.client.get('/projects/').content.decode()

        self.assertEqual(body.count('aria-label="View project: '), 1)
        self.assertIn('href="https://example.com/case-study"', body)
        self.assertIn('rel="noopener noreferrer"', body)
        self.assertIn('target="_blank"', body)
        self.assertEqual(body.count('View Project'), 1)  # the hover button, only on the linked card

    def test_card_shows_the_highlight_badge_only_when_set(self):
        with_badge = render_to_string(
            'components/project-card.html', {'p': make_project(title='With badge', highlight='+42% conversion')}
        )
        without_badge = render_to_string(
            'components/project-card.html', {'p': make_project(title='Without badge')}
        )

        self.assertIn('+42% conversion', with_badge)
        self.assertIn('ring-primary/20', with_badge)
        self.assertNotIn('ring-primary/20', without_badge)

    def test_card_uses_the_uploaded_picture(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            project = make_project(title='Pictured')
            project.image.save('shot.png', make_image(), save=True)

            body = self.client.get('/projects/').content.decode()

        self.assertIn(project.image.url, body)

    def test_card_uses_the_built_in_picture_when_nothing_is_uploaded(self):
        make_project(title='Seeded', static_image='/assets/images/project-2.jpg')

        self.assertContains(self.client.get('/projects/'), 'src="/assets/images/project-2.jpg"')

    def test_card_falls_back_to_an_initial_when_there_is_no_picture(self):
        card = render_to_string('components/project-card.html', {'p': make_project(title='Zebra Platform')})

        self.assertNotIn('<img', card)
        self.assertIn('aria-hidden="true"', card)
        self.assertRegex(card, r'>\s*Z\s*</div>')

    def test_category_link_deep_links_to_the_filtered_projects_page(self):
        make_project(title='Branded', category='Digital Marketing')

        self.assertContains(
            self.client.get('/projects/'),
            'href="/projects/?category=Digital%20Marketing"',
        )

    def test_html_in_project_text_is_escaped(self):
        make_project(
            title='<script>alert(1)</script>',
            description='<img src=x onerror=alert(2)>',
            category='<b>Cat</b>',
            highlight='<i>hot</i>',
        )

        for url in ('/projects/', '/'):
            body = self.client.get(url).content.decode()

            self.assertNotIn('<script>alert(1)</script>', body)
            self.assertNotIn('<img src=x onerror=alert(2)>', body)
            self.assertNotIn('<b>Cat</b>', body)
            self.assertNotIn('<i>hot</i>', body)

    def test_homepage_carousel_shows_only_published_projects_flagged_for_home(self):
        make_project(title='On the homepage')
        make_project(title='Projects page only', show_on_home=False)
        make_project(title='Hidden entirely', is_published=False, show_on_home=True)

        body = self.client.get('/').content.decode()

        self.assertIn('On the homepage', body)
        self.assertNotIn('Projects page only', body)
        self.assertNotIn('Hidden entirely', body)

    def test_homepage_projects_section_disappears_with_no_projects(self):
        body = self.client.get('/').content.decode()

        # (the page's script and styles mention these names regardless; look
        # for the actual element)
        self.assertNotIn('class="swiper project-swiper', body)
        self.assertNotIn('x-data="projectsCarousel()"', body)

    def test_homepage_carousel_is_limited_to_the_most_recent_twelve(self):
        for number in range(15):
            make_project(title=f'Project {number}', sort_order=number + 1)

        self.assertEqual(len(self.client.get('/').context['home_projects']), 12)

    def test_homepage_carousel_follows_the_dashboard_order(self):
        make_project(title='Second', sort_order=2)
        make_project(title='First', sort_order=1)

        titles = [p.title for p in self.client.get('/').context['home_projects']]

        self.assertEqual(titles, ['First', 'Second'])


class AdminPageTests(TestCase):
    def test_dashboard_page_redirects_anonymous_visitors_to_login(self):
        response = self.client.get('/admin-dashboard/projects')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/login', response['Location'])

    def test_dashboard_page_renders_for_a_logged_in_user(self):
        self.client.force_login(User.objects.create_user('editor', password='x', is_staff=True))

        response = self.client.get('/admin-dashboard/projects')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New project')


class AdminApiTests(EmptyTableTestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.staff = User.objects.create_user('editor', password='x', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def stored_files(self):
        return [p for p in Path(self.media_root).rglob('*') if p.is_file()]

    def valid_payload(self, **overrides):
        payload = {
            'title': 'New Portal',
            'category': 'Web Development',
            'description': 'Built for a client.',
        }
        payload.update(overrides)
        return payload

    # access

    def test_anonymous_requests_are_rejected(self):
        anonymous = APIClient()

        self.assertIn(anonymous.get(API_URL).status_code, (401, 403))
        self.assertIn(anonymous.post(API_URL, self.valid_payload(), format='json').status_code, (401, 403))
        self.assertIn(anonymous.post(f'{API_URL}reorder/', {'ids': []}, format='json').status_code, (401, 403))

    def test_non_staff_users_are_rejected(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user('visitor', password='x'))

        self.assertEqual(client.get(API_URL).status_code, 403)
        self.assertEqual(client.post(API_URL, self.valid_payload(), format='json').status_code, 403)
        self.assertEqual(client.post(f'{API_URL}reorder/', {'ids': []}, format='json').status_code, 403)

    # create / read

    def test_create_with_json(self):
        response = self.client.post(API_URL, self.valid_payload(
            highlight='+10% sales', link_url='https://example.com',
        ), format='json')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['title'], 'New Portal')
        self.assertEqual(response.data['highlight'], '+10% sales')
        self.assertTrue(response.data['is_published'])
        self.assertTrue(response.data['show_on_home'])
        self.assertEqual(response.data['image_url'], '')

    def test_a_new_project_goes_to_the_top(self):
        older = make_project(title='Older', sort_order=1)

        response = self.client.post(API_URL, self.valid_payload(title='Newest'), format='json')

        titles = [p['title'] for p in self.client.get(API_URL).data]
        self.assertEqual(titles, ['Newest', 'Older'])
        self.assertEqual(response.data['sort_order'], 0)
        self.assertLess(response.data['sort_order'], older.sort_order)

    def test_create_with_an_image(self):
        response = self.client.post(API_URL, {
            **self.valid_payload(), 'image': make_image(), 'is_published': 'true',
        }, format='multipart')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.data['image_url'].startswith('http'))
        self.assertIn('/media/projects/', response.data['image_url'])
        self.assertEqual(len(self.stored_files()), 1)
        self.assertNotIn('image', response.data)

    def test_multipart_booleans_are_read_as_sent(self):
        response = self.client.post(API_URL, {
            **self.valid_payload(), 'is_published': 'false', 'show_on_home': 'false',
        }, format='multipart')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(response.data['is_published'])
        self.assertFalse(response.data['show_on_home'])

    def test_list_includes_hidden_projects(self):
        make_project(title='Live')
        make_project(title='Hidden', is_published=False)

        response = self.client.get(API_URL)

        self.assertEqual({p['title'] for p in response.data}, {'Live', 'Hidden'})

    def test_builtin_picture_is_exposed_as_an_absolute_url(self):
        make_project(static_image='/assets/images/project-1.jpg')

        url = self.client.get(API_URL).data[0]['image_url']

        self.assertTrue(url.startswith('http'))
        self.assertTrue(url.endswith('/assets/images/project-1.jpg'))

    # validation

    def test_required_fields(self):
        response = self.client.post(API_URL, {'title': '  ', 'category': ' ', 'description': ''}, format='json')

        self.assertEqual(response.status_code, 400)
        for field in ('title', 'category', 'description'):
            self.assertIn(field, response.data)

    def test_category_reuses_the_existing_spelling_when_only_the_case_differs(self):
        make_project(category='Branding')

        response = self.client.post(API_URL, self.valid_payload(category='  branding '), format='json')

        self.assertEqual(response.data['category'], 'Branding')
        self.assertEqual(Project.objects.values('category').distinct().count(), 1)

    def test_category_collapses_extra_spaces(self):
        response = self.client.post(API_URL, self.valid_payload(category='Web   App \t Development'), format='json')

        self.assertEqual(response.data['category'], 'Web App Development')

    def test_a_genuinely_new_category_is_kept_as_typed(self):
        response = self.client.post(API_URL, self.valid_payload(category='CCTV & Security'), format='json')

        self.assertEqual(response.data['category'], 'CCTV & Security')

    def test_link_must_be_a_web_address(self):
        for bad in ('javascript:alert(1)', 'data:text/html,hi', 'ftp://example.com/x', 'example.com', 'not a url'):
            response = self.client.post(API_URL, self.valid_payload(link_url=bad), format='json')

            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('link_url', response.data, bad)
            # The same helpful wording whichever check catches it first.
            self.assertIn('http://', str(response.data['link_url']), bad)

        self.assertEqual(Project.objects.count(), 0)

    def test_link_is_optional_and_http_and_https_are_accepted(self):
        for good in ('', 'http://example.com', 'https://example.com/a?b=c#d'):
            response = self.client.post(API_URL, self.valid_payload(link_url=good), format='json')

            self.assertEqual(response.status_code, 201, good)

    def test_a_non_image_upload_is_rejected(self):
        response = self.client.post(API_URL, {
            **self.valid_payload(),
            'image': SimpleUploadedFile('notes.txt', b'not an image', content_type='text/plain'),
        }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('image', response.data)
        self.assertEqual(self.stored_files(), [])

    def test_a_script_carrying_svg_is_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

        response = self.client.post(API_URL, {
            **self.valid_payload(),
            'image': SimpleUploadedFile('evil.svg', svg, content_type='image/svg+xml'),
        }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stored_files(), [])

    def test_an_oversized_image_is_rejected(self):
        with patch('projects.serializers.IMAGE_MAX_BYTES', 10):
            response = self.client.post(API_URL, {
                **self.valid_payload(), 'image': make_image(),
            }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('5 MB', str(response.data['image']))
        self.assertEqual(self.stored_files(), [])

    # update

    def test_partial_update_toggles_the_switches(self):
        project = make_project()

        response = self.client.patch(
            f'{API_URL}{project.pk}/', {'is_published': False, 'show_on_home': False}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertFalse(project.is_published)
        self.assertFalse(project.show_on_home)

    def test_sort_order_cannot_be_set_through_the_normal_endpoint(self):
        project = make_project(sort_order=3)

        self.client.patch(f'{API_URL}{project.pk}/', {'sort_order': 99}, format='json')

        project.refresh_from_db()
        self.assertEqual(project.sort_order, 3)

    def test_uploading_a_picture_replaces_the_built_in_one(self):
        project = make_project(static_image='/assets/images/project-1.jpg')

        response = self.client.patch(
            f'{API_URL}{project.pk}/', {'image': make_image()}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        project.refresh_from_db()
        self.assertEqual(project.static_image, '')
        self.assertIn('/media/projects/', response.data['image_url'])

    def test_removing_the_picture_also_clears_the_built_in_one(self):
        project = make_project(static_image='/assets/images/project-1.jpg')

        response = self.client.patch(
            f'{API_URL}{project.pk}/', {'remove_image': 'true'}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['image_url'], '')
        project.refresh_from_db()
        self.assertEqual(project.static_image, '')

    def test_editing_text_keeps_the_built_in_picture(self):
        project = make_project(static_image='/assets/images/project-1.jpg')

        self.client.patch(f'{API_URL}{project.pk}/', {'title': 'Renamed'}, format='json')

        project.refresh_from_db()
        self.assertEqual(project.static_image, '/assets/images/project-1.jpg')

    def test_replacing_an_upload_deletes_the_old_file(self):
        created = self.client.post(API_URL, {
            **self.valid_payload(), 'image': make_image('one.png'),
        }, format='multipart')
        first_file = self.stored_files()[0]

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'image': make_image('two.png')}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        files = self.stored_files()
        self.assertEqual(len(files), 1)
        self.assertNotEqual(files[0], first_file)

    def test_removing_an_upload_deletes_the_file(self):
        created = self.client.post(API_URL, {
            **self.valid_payload(), 'image': make_image(),
        }, format='multipart')

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'remove_image': 'true'}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['image_url'], '')
        self.assertEqual(self.stored_files(), [])

    def test_editing_text_leaves_an_upload_alone(self):
        created = self.client.post(API_URL, {
            **self.valid_payload(), 'image': make_image(),
        }, format='multipart')

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'description': 'New text'}, format='multipart'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['image_url'])
        self.assertEqual(len(self.stored_files()), 1)

    # delete

    def test_delete_removes_the_record_and_its_upload(self):
        created = self.client.post(API_URL, {
            **self.valid_payload(), 'image': make_image(),
        }, format='multipart')

        response = self.client.delete(f"{API_URL}{created.data['id']}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Project.objects.exists())
        self.assertEqual(self.stored_files(), [])

    def test_delete_without_an_upload(self):
        project = make_project(static_image='/assets/images/project-1.jpg')

        self.assertEqual(self.client.delete(f'{API_URL}{project.pk}/').status_code, 204)
        self.assertFalse(Project.objects.exists())

    # reorder

    def test_reorder_sets_the_new_order_and_returns_it(self):
        a, b, c = (make_project(title=t, sort_order=i) for i, t in enumerate('ABC', start=1))

        response = self.client.post(f'{API_URL}reorder/', {'ids': [c.pk, a.pk, b.pk]}, format='json')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([p['title'] for p in response.data], ['C', 'A', 'B'])
        self.assertEqual(
            list(Project.objects.values_list('title', 'sort_order')),
            [('C', 1), ('A', 2), ('B', 3)],
        )

    def test_a_project_added_after_reordering_still_lands_on_top(self):
        a, b = make_project(title='A'), make_project(title='B')
        self.client.post(f'{API_URL}reorder/', {'ids': [a.pk, b.pk]}, format='json')

        self.client.post(API_URL, self.valid_payload(title='Fresh'), format='json')

        self.assertEqual([p['title'] for p in self.client.get(API_URL).data][0], 'Fresh')

    def test_reorder_changes_the_public_order(self):
        a, b = make_project(title='A', sort_order=1), make_project(title='B', sort_order=2)

        self.client.post(f'{API_URL}reorder/', {'ids': [b.pk, a.pk]}, format='json')

        titles = [p.title for p in self.client.get('/projects/').context['projects']]
        self.assertEqual(titles, ['B', 'A'])

    def test_reorder_rejects_an_incomplete_list(self):
        a, b = make_project(title='A', sort_order=1), make_project(title='B', sort_order=2)

        response = self.client.post(f'{API_URL}reorder/', {'ids': [b.pk]}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            list(Project.objects.values_list('title', 'sort_order')),
            [('A', 1), ('B', 2)],
        )

    def test_reorder_rejects_unknown_and_duplicate_ids(self):
        a = make_project(title='A', sort_order=1)

        self.assertEqual(self.client.post(f'{API_URL}reorder/', {'ids': [a.pk, 9999]}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'{API_URL}reorder/', {'ids': [a.pk, a.pk]}, format='json').status_code, 400)

    def test_reorder_rejects_malformed_input(self):
        make_project()

        for payload in ({}, {'ids': 'abc'}, {'ids': ['1']}, {'ids': [True]}, {'ids': None}, {'ids': [1.5]}):
            response = self.client.post(f'{API_URL}reorder/', payload, format='json')

            self.assertEqual(response.status_code, 400, payload)
