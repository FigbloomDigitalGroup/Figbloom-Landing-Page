import re
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


def hero_html(body):
    """The hero section's HTML out of a rendered /activities/ page."""
    return body.split('<section class="act-hero">')[1].split('</section>')[0]


def collage_photos(body):
    """The photo addresses in the hero collage, in the order the page shows them
    (the first is the big frame)."""
    collage = hero_html(body).split('class="act-collage"')[1]
    return re.findall(r'<img src="([^"]+)"', collage)


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
        make_activity(title='An event', category='event')

        response = self.client.get('/activities/')

        # Chips are the buttons that switch the filter; the hero's decorative
        # tiles legitimately mention every category, so look at the chips only.
        self.assertContains(response, "category = 'event'")
        self.assertNotContains(response, "category = 'update'")
        self.assertNotContains(response, "category = 'achievement'")
        self.assertEqual([c['key'] for c in response.context['categories']], ['event'])
        self.assertEqual(response.context['categories'][0]['count'], 1)

    def test_the_tabs_are_all_events_updates_community_and_achievements(self):
        for category in ('event', 'update', 'community', 'achievement', 'workshop'):
            make_activity(title=f'A {category}', category=category)

        response = self.client.get('/activities/')

        self.assertEqual(
            [c['key'] for c in response.context['categories']],
            ['event', 'update', 'community', 'achievement'],
        )
        self.assertEqual(
            [c['plural'] for c in response.context['categories']],
            ['Events', 'Updates', 'Community', 'Achievements'],
        )
        self.assertContains(response, 'All Activities')
        self.assertNotContains(response, "category = 'workshop'")
        # five buttons in the filter row: All + the four categories
        self.assertEqual(response.content.decode().count('class="act-chip"'), 5)

    def test_workshops_still_show_under_all_activities_without_a_tab(self):
        make_activity(title='Security basics', category='workshop')
        make_activity(title='Plain event', category='event')

        response = self.client.get('/activities/')

        self.assertContains(response, 'Security basics')
        self.assertEqual(response.context['total'], 2)
        # ...with their own label on the card, even though they have no tab
        self.assertContains(response, 'Workshop</span>')

    def test_team_activities_are_posted_as_updates_and_show_under_that_tab(self):
        make_activity(title='Friday pairing session', category='update')
        make_activity(title='Plain event', category='event')

        response = self.client.get('/activities/')

        update_tab = next(c for c in response.context['categories'] if c['key'] == 'update')
        self.assertEqual(update_tab['count'], 1)
        self.assertContains(response, 'Friday pairing session')
        self.assertContains(response, 'data-category="update"')

    def test_a_site_with_only_untabbed_categories_still_lists_everything(self):
        make_activity(title='Only a workshop', category='workshop')

        response = self.client.get('/activities/')

        self.assertContains(response, 'Only a workshop')
        self.assertEqual(response.context['categories'], [])
        self.assertContains(response, 'All Activities')

    def page_with_covers(self, *activities):
        """Makes one activity per (title, fields) pair, each with its own cover
        picture, and returns the rendered /activities/ page."""
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            made = []
            for title, fields in activities:
                activity = make_activity(title=title, **fields)
                activity.cover_image.save(f'{activity.slug}.png', make_image(), save=True)
                made.append(activity)
            body = self.client.get('/activities/').content.decode()

        return made, body

    def test_hero_has_the_heading_stats_and_button_beside_a_photo_collage(self):
        _, body = self.page_with_covers(('Digital Skills Day', {}))
        hero = hero_html(body)

        self.assertIn('Our Activities</span>', hero)
        self.assertIn('Our Journey in <em>Action</em>', hero)
        self.assertIn('aria-label="At a glance"', hero)
        self.assertIn('href="#browse"', hero)
        self.assertIn('class="act-collage"', hero)

    def test_hero_collage_is_decorative_and_has_three_photo_frames(self):
        _, body = self.page_with_covers(('One', {}), ('Two', {}), ('Three', {}), ('Four', {}))
        collage = hero_html(body).split('class="act-collage"')[1]

        self.assertIn('aria-hidden="true"', hero_html(body).split('class="act-collage"')[1][:40])
        self.assertEqual(collage.count('class="act-collage__item '), 3)
        self.assertEqual(len(collage_photos(body)), 3)

    def test_hero_collage_always_shows_the_same_fixed_site_photos(self):
        from .views import HERO_PHOTOS

        made, body = self.page_with_covers(
            ('Oldest', {'activity_date': date(2026, 1, 1)}),
            ('Featured', {'is_featured': True, 'activity_date': date(2026, 6, 1)}),
            ('Newest', {'activity_date': date(2026, 9, 1)}),
        )

        self.assertEqual(collage_photos(body), HERO_PHOTOS)
        for activity in made:
            self.assertNotIn(activity.cover_image.url, hero_html(body))

    def test_replacing_an_activity_cover_does_not_change_the_hero(self):
        from .views import HERO_PHOTOS

        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            activity = make_activity(title='Vision Expo')
            activity.cover_image.save('first.png', make_image(), save=True)
            before = collage_photos(self.client.get('/activities/').content.decode())

            activity.cover_image.save('second.png', make_image(), save=True)
            body = self.client.get('/activities/').content.decode()

        self.assertEqual(before, HERO_PHOTOS)
        self.assertEqual(collage_photos(body), HERO_PHOTOS)
        self.assertNotIn(activity.cover_image.url, hero_html(body))
        # ...while the activity's own card further down does show the new cover
        self.assertIn(activity.cover_image.url, body)

    def test_hero_collage_is_the_same_when_there_are_no_activities(self):
        from .views import HERO_PHOTOS

        body = self.client.get('/activities/').content.decode()

        self.assertEqual(collage_photos(body), HERO_PHOTOS)
        self.assertNotIn('aria-label="At a glance"', hero_html(body))  # no numbers to show yet

    def test_activities_without_a_cover_do_not_change_the_hero(self):
        from .views import HERO_PHOTOS

        make_activity(title='No picture here')

        photos = collage_photos(self.client.get('/activities/').content.decode())

        self.assertEqual(photos, HERO_PHOTOS)

    def test_the_hero_photos_are_real_site_images(self):
        from django.conf import settings

        from .views import HERO_PHOTOS

        for photo in HERO_PHOTOS:
            self.assertTrue(photo.startswith('/assets/images/'), photo)
            self.assertTrue((Path(settings.FRONTEND_DIR) / photo.lstrip('/')).is_file(), photo)

    def test_hero_carries_no_text_about_a_single_activity(self):
        made, body = self.page_with_covers(
            ('Digital Skills Day', {'is_featured': True, 'location': 'Nairobi'}),
        )
        hero = hero_html(body)

        self.assertNotIn('Digital Skills Day', hero)
        self.assertNotIn('Nairobi', hero)
        self.assertNotIn(made[0].get_absolute_url(), hero)

    def test_an_unpublished_featured_activity_never_reaches_the_hero(self):
        from .views import HERO_PHOTOS

        made, body = self.page_with_covers(
            ('Secret star', {'is_featured': True, 'is_published': False}),
            ('Public one', {}),
        )
        secret, public = made

        self.assertEqual(collage_photos(body), HERO_PHOTOS)
        self.assertNotIn(secret.cover_image.url, body)
        self.assertNotContains(self.client.get('/activities/'), 'Secret star')

    def test_the_featured_activity_is_still_listed_with_everything_else(self):
        make_activity(title='Starred', is_featured=True)
        make_activity(title='Plain')

        body = self.client.get('/activities/').content.decode()

        self.assertEqual(body.count('data-activity\n'), 2)  # both cards are in the list
        self.assertNotIn('data-spotlighted', body)

    def test_shortcut_strip_offers_the_four_themes_in_order(self):
        response = self.client.get('/activities/')
        body = response.content.decode()

        self.assertEqual(
            [h['key'] for h in response.context['highlights']],
            ['update', 'event', 'community', 'achievement'],
        )
        for key, title in (('update', 'Stories'), ('event', 'Events'), ('community', 'Community'), ('achievement', 'Impact')):
            self.assertIn(f'data-filter="{key}"', body)
            self.assertIn(f'href="/activities/?category={key}#browse"', body)
            self.assertIn(f'>{title}</span>', body)

    def test_every_shortcut_points_at_a_category_that_has_a_tab(self):
        from .categories import CATEGORY_BY_KEY
        from .views import HIGHLIGHTS

        for highlight in HIGHLIGHTS:
            self.assertTrue(CATEGORY_BY_KEY[highlight['key']]['tab'], highlight['key'])

    def test_the_shortcuts_and_the_hero_button_have_somewhere_to_land(self):
        body = self.client.get('/activities/').content.decode()

        self.assertIn('id="browse"', body)
        self.assertIn('href="#browse"', body)  # the "Explore Our Activities" button

    def test_every_category_declares_whether_it_has_a_tab(self):
        from .categories import CATEGORIES

        self.assertTrue(all(isinstance(c['tab'], bool) for c in CATEGORIES))
        self.assertEqual(
            [c['key'] for c in CATEGORIES if c['tab']],
            ['event', 'update', 'community', 'achievement'],
        )

    def test_unknown_or_untabbed_category_in_the_address_is_harmless(self):
        make_activity(title='A workshop', category='workshop')

        # The page itself still renders; the script ignores categories that
        # have no tab and shows everything.
        for category in ('workshop', 'team', 'bogus'):
            self.assertEqual(self.client.get(f'/activities/?category={category}').status_code, 200)

    def test_detail_page_links_to_the_category_tab_when_there_is_one(self):
        activity = make_activity(title='Main event', category='event')
        make_activity(title='Another event', category='event')

        response = self.client.get(activity.get_absolute_url())

        self.assertContains(response, 'href="/activities/?category=event"')
        self.assertContains(response, 'More events')

    def test_detail_page_does_not_point_at_a_tab_that_does_not_exist(self):
        activity = make_activity(title='Security basics', category='workshop')
        make_activity(title='Another workshop', category='workshop')

        response = self.client.get(activity.get_absolute_url())

        self.assertNotContains(response, 'category=workshop')
        self.assertNotContains(response, 'More workshops')
        self.assertContains(response, 'All activities')

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

class AdminPageTests(TestCase):
    def test_dashboard_page_redirects_anonymous_visitors_to_login(self):
        response = self.client.get('/admin-dashboard/activities')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-dashboard/login', response['Location'])

    def test_dashboard_page_renders_for_a_logged_in_user(self):
        self.client.force_login(User.objects.create_user('editor', password='x', is_staff=True))

        response = self.client.get('/admin-dashboard/activities')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Workshop')


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

    def test_the_old_team_category_is_no_longer_accepted(self):
        response = self.client.post(API_URL, {
            'title': 'x', 'summary': 'y', 'category': 'team',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.data)

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


class TeamActivityMigrationTests(TestCase):
    """Team activities were folded into Updates; entries filed under the old
    category must come along rather than be stranded."""

    def test_existing_team_entries_move_to_updates_and_nothing_else_changes(self):
        import importlib

        from django.apps import apps

        module = importlib.import_module('activities.migrations.0002_move_team_activities_to_updates')
        team = make_activity(title='Friday pairing', category='team')  # the old value
        event = make_activity(title='Tech talk', category='event')
        workshop = make_activity(title='Security basics', category='workshop')

        module.move_team_activities_to_updates(apps, None)

        for activity, expected in ((team, 'update'), (event, 'event'), (workshop, 'workshop')):
            activity.refresh_from_db()
            self.assertEqual(activity.category, expected, activity.title)

    def test_moved_entries_show_under_the_updates_tab(self):
        import importlib

        from django.apps import apps

        module = importlib.import_module('activities.migrations.0002_move_team_activities_to_updates')
        make_activity(title='Friday pairing', category='team')

        module.move_team_activities_to_updates(apps, None)
        response = self.client.get('/activities/')

        self.assertEqual([c['key'] for c in response.context['categories']], ['update'])
        self.assertContains(response, 'Friday pairing')
