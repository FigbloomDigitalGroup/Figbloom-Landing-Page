import shutil
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from .models import Activity

User = get_user_model()

API_URL = '/api/admin/activities/'


def make_image(name='cover.png', size=(40, 30)):
    buffer = BytesIO()
    Image.new('RGB', size, (255, 148, 0)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def make_activity(**overrides):
    fields = {
        'title': 'Tech Talk',
        'category': 'event',
        'summary': 'An evening of talks.',
        'activity_date': date(2026, 10, 15),
    }
    fields.update(overrides)
    return Activity.objects.create(**fields)


class ActivityModelTests(TestCase):
    def test_slug_is_generated_from_the_title(self):
        self.assertEqual(make_activity(title='Figbloom Tech Talk 2026').slug, 'figbloom-tech-talk-2026')

    def test_duplicate_titles_get_distinct_slugs(self):
        first = make_activity(title='Open Day')
        second = make_activity(title='Open Day')
        third = make_activity(title='Open Day')

        self.assertEqual(first.slug, 'open-day')
        self.assertEqual(second.slug, 'open-day-2')
        self.assertEqual(third.slug, 'open-day-3')

    def test_slug_does_not_change_when_the_title_is_edited(self):
        activity = make_activity(title='Open Day')
        activity.title = 'Open Day (corrected)'
        activity.save()

        self.assertEqual(Activity.objects.get(pk=activity.pk).slug, 'open-day')

    def test_a_title_with_no_sluggable_characters_still_saves(self):
        self.assertEqual(make_activity(title='!!!').slug, 'activity')

    def test_published_excludes_drafts(self):
        live = make_activity(title='Live')
        make_activity(title='Draft', is_published=False)

        self.assertEqual(list(Activity.objects.published()), [live])

    def test_newest_activity_date_comes_first(self):
        older = make_activity(title='Older', activity_date=date(2026, 1, 1))
        newer = make_activity(title='Newer', activity_date=date(2026, 6, 1))

        self.assertEqual(list(Activity.objects.all()), [newer, older])

    def test_paragraphs_split_on_blank_lines(self):
        activity = make_activity(content='First.\n\n\nSecond line one\nsecond line two.\n\n  \nThird.')

        self.assertEqual(
            activity.paragraphs,
            ['First.', 'Second line one\nsecond line two.', 'Third.'],
        )

    def test_paragraphs_of_empty_content(self):
        self.assertEqual(make_activity(content='').paragraphs, [])


class PublicPageTests(TestCase):
    def test_empty_state_when_nothing_is_published(self):
        make_activity(title='Hidden draft', is_published=False)

        response = self.client.get('/activities/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stories are on the way')
        self.assertNotContains(response, 'Hidden draft')

    def test_trailing_slash_is_optional(self):
        self.assertEqual(self.client.get('/activities').status_code, 200)

    def test_list_shows_published_and_hides_drafts(self):
        make_activity(title='Visible talk')
        make_activity(title='Secret draft', is_published=False)

        response = self.client.get('/activities/')

        self.assertContains(response, 'Visible talk')
        self.assertNotContains(response, 'Secret draft')

    def test_filter_chips_only_for_categories_that_have_activities(self):
        make_activity(title='A workshop', category='workshop')

        response = self.client.get('/activities/')

        # Chips are the buttons that switch the filter; the hero's decorative
        # tiles legitimately mention every category, so look at the chips only.
        self.assertContains(response, "category = 'workshop'")
        self.assertNotContains(response, "category = 'team'")
        self.assertNotContains(response, "category = 'achievement'")
        self.assertEqual([c['key'] for c in response.context['categories']], ['workshop'])
        self.assertEqual(response.context['categories'][0]['count'], 1)

    def test_list_escapes_html_in_titles_and_summaries(self):
        make_activity(title='<script>alert(1)</script>', summary='<img src=x onerror=alert(2)>')

        body = self.client.get('/activities/').content.decode()

        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertNotIn('<img src=x onerror=alert(2)>', body)

    def test_detail_page_renders_a_published_activity(self):
        activity = make_activity(
            title='Digital Skills Workshop',
            category='workshop',
            content='Paragraph one.\n\nParagraph two.',
            location='Nairobi',
        )

        response = self.client.get(activity.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Digital Skills Workshop')
        self.assertContains(response, 'Paragraph one.')
        self.assertContains(response, 'Paragraph two.')
        self.assertContains(response, 'Nairobi')

    def test_detail_page_escapes_html_in_content(self):
        activity = make_activity(content='<script>alert(1)</script>\n\n<b>bold</b>')

        body = self.client.get(activity.get_absolute_url()).content.decode()

        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertNotIn('<b>bold</b>', body)
        self.assertIn('&lt;b&gt;bold&lt;/b&gt;', body)

    def test_detail_page_is_a_404_for_a_draft_when_logged_out(self):
        draft = make_activity(is_published=False)

        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

    def test_detail_page_is_a_404_for_a_draft_for_non_staff(self):
        draft = make_activity(is_published=False)
        self.client.force_login(User.objects.create_user('visitor', password='x'))

        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

    def test_staff_can_preview_a_draft(self):
        draft = make_activity(title='Upcoming reveal', is_published=False)
        self.client.force_login(User.objects.create_user('editor', password='x', is_staff=True))

        response = self.client.get(draft.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Upcoming reveal')
        self.assertContains(response, 'Draft preview')

    def test_unknown_slug_is_a_404(self):
        self.assertEqual(self.client.get('/activities/no-such-thing/').status_code, 404)

    def test_related_activities_are_offered_without_repeating_the_current_one(self):
        current = make_activity(title='Current one', category='event')
        make_activity(title='Sibling event', category='event')
        make_activity(title='Other category item', category='update')

        response = self.client.get(current.get_absolute_url())

        self.assertContains(response, 'Sibling event')
        self.assertContains(response, 'Other category item')  # topped up from elsewhere
        self.assertNotIn('Current one', [a.title for a in response.context['related']])

    def test_featured_activity_is_spotlighted(self):
        make_activity(title='Ordinary')
        make_activity(title='The big one', is_featured=True)

        response = self.client.get('/activities/')

        self.assertEqual(response.context['featured'].title, 'The big one')

    def test_unpublished_featured_activity_is_not_spotlighted(self):
        make_activity(title='Draft star', is_featured=True, is_published=False)

        self.assertIsNone(self.client.get('/activities/').context['featured'])


class AdminPageTests(TestCase):
    def test_dashboard_page_redirects_anonymous_visitors_to_login(self):
        response = self.client.get('/admin-dashboard/activities')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/login', response['Location'])

    def test_dashboard_page_renders_for_a_logged_in_user(self):
        self.client.force_login(User.objects.create_user('editor', password='x', is_staff=True))

        response = self.client.get('/admin-dashboard/activities')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Team Activity')


class AdminApiTests(TestCase):
    def setUp(self):
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

    # access

    def test_anonymous_requests_are_rejected(self):
        anonymous = APIClient()

        self.assertIn(anonymous.get(API_URL).status_code, (401, 403))
        self.assertIn(anonymous.post(API_URL, {'title': 'x'}, format='json').status_code, (401, 403))

    def test_non_staff_users_are_rejected(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user('visitor', password='x'))

        self.assertEqual(client.get(API_URL).status_code, 403)
        self.assertEqual(client.post(API_URL, {'title': 'x'}, format='json').status_code, 403)

    # create / read

    def test_create_with_json(self):
        response = self.client.post(API_URL, {
            'title': 'Community Clean-up',
            'category': 'community',
            'summary': 'We cleaned up the estate.',
            'activity_date': '2026-09-20',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['slug'], 'community-clean-up')
        self.assertEqual(response.data['category_label'], 'Community')
        self.assertEqual(response.data['public_url'], '/activities/community-clean-up/')
        self.assertTrue(response.data['is_published'])  # visible unless unticked
        self.assertEqual(response.data['image_url'], '')

    def test_create_with_a_cover_image(self):
        response = self.client.post(API_URL, {
            'title': 'With photo',
            'category': 'event',
            'summary': 'Has a cover.',
            'activity_date': '2026-09-20',
            'is_published': 'true',
            'cover_image': make_image(),
        }, format='multipart')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn('/media/activities/', response.data['image_url'])
        self.assertTrue(response.data['image_url'].startswith('http'))
        self.assertEqual(len(self.stored_files()), 1)
        self.assertNotIn('cover_image', response.data)

    def test_multipart_booleans_are_read_as_sent(self):
        response = self.client.post(API_URL, {
            'title': 'Draft via form',
            'category': 'update',
            'summary': 'Not live yet.',
            'activity_date': '2026-09-20',
            'is_published': 'false',
            'is_featured': 'true',
        }, format='multipart')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(response.data['is_published'])
        self.assertTrue(response.data['is_featured'])

    def test_list_includes_drafts(self):
        make_activity(title='Live')
        make_activity(title='Draft', is_published=False)

        response = self.client.get(API_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({a['title'] for a in response.data}, {'Live', 'Draft'})

    # validation

    def test_required_fields(self):
        response = self.client.post(API_URL, {'title': '   ', 'summary': ''}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('title', response.data)
        self.assertIn('summary', response.data)

    def test_unknown_category_is_rejected(self):
        response = self.client.post(API_URL, {
            'title': 'x', 'summary': 'y', 'category': 'nonsense',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.data)

    def test_a_non_image_upload_is_rejected(self):
        response = self.client.post(API_URL, {
            'title': 'x',
            'summary': 'y',
            'cover_image': SimpleUploadedFile('notes.txt', b'not an image', content_type='text/plain'),
        }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('cover_image', response.data)
        self.assertEqual(self.stored_files(), [])

    def test_a_script_carrying_svg_is_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

        response = self.client.post(API_URL, {
            'title': 'x',
            'summary': 'y',
            'cover_image': SimpleUploadedFile('evil.svg', svg, content_type='image/svg+xml'),
        }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stored_files(), [])

    def test_an_oversized_image_is_rejected(self):
        # Shrink the limit rather than build a 5 MB image: any real PNG is
        # bigger than 10 bytes.
        with patch('activities.serializers.COVER_MAX_BYTES', 10):
            response = self.client.post(API_URL, {
                'title': 'x', 'summary': 'y', 'cover_image': make_image(),
            }, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('5 MB', str(response.data['cover_image']))
        self.assertEqual(self.stored_files(), [])

    # update

    def test_partial_update_toggles_publish_and_feature(self):
        activity = make_activity()

        response = self.client.patch(
            f'{API_URL}{activity.pk}/', {'is_published': False, 'is_featured': True}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        activity.refresh_from_db()
        self.assertFalse(activity.is_published)
        self.assertTrue(activity.is_featured)

    def test_editing_the_title_keeps_the_slug(self):
        activity = make_activity(title='Original')

        response = self.client.patch(f'{API_URL}{activity.pk}/', {'title': 'Renamed'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['slug'], 'original')

    def test_slug_cannot_be_set_through_the_api(self):
        activity = make_activity(title='Original')

        self.client.patch(f'{API_URL}{activity.pk}/', {'slug': 'hijacked'}, format='json')

        activity.refresh_from_db()
        self.assertEqual(activity.slug, 'original')

    def test_replacing_the_image_deletes_the_old_file(self):
        created = self.client.post(API_URL, {
            'title': 'Photo', 'summary': 'y', 'cover_image': make_image('one.png'),
        }, format='multipart')
        self.assertEqual(len(self.stored_files()), 1)
        first_file = self.stored_files()[0]

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'cover_image': make_image('two.png')}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        files = self.stored_files()
        self.assertEqual(len(files), 1)
        self.assertNotEqual(files[0], first_file)
        self.assertTrue(response.data['image_url'])

    def test_remove_image_clears_the_cover_and_deletes_the_file(self):
        created = self.client.post(API_URL, {
            'title': 'Photo', 'summary': 'y', 'cover_image': make_image(),
        }, format='multipart')

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'remove_image': 'true'}, format='multipart'
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['image_url'], '')
        self.assertEqual(self.stored_files(), [])

    def test_editing_text_leaves_the_image_alone(self):
        created = self.client.post(API_URL, {
            'title': 'Photo', 'summary': 'y', 'cover_image': make_image(),
        }, format='multipart')

        response = self.client.patch(
            f"{API_URL}{created.data['id']}/", {'summary': 'New summary'}, format='multipart'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['image_url'])
        self.assertEqual(len(self.stored_files()), 1)

    # delete

    def test_delete_removes_the_record_and_its_image(self):
        created = self.client.post(API_URL, {
            'title': 'Photo', 'summary': 'y', 'cover_image': make_image(),
        }, format='multipart')

        response = self.client.delete(f"{API_URL}{created.data['id']}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Activity.objects.exists())
        self.assertEqual(self.stored_files(), [])

    def test_delete_without_an_image(self):
        activity = make_activity()

        self.assertEqual(self.client.delete(f'{API_URL}{activity.pk}/').status_code, 204)
        self.assertFalse(Activity.objects.exists())
