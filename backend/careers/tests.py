from datetime import timedelta
from unittest.mock import patch

from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Job, JobApplication


class _ImmediateThread:
    """Stand-in for threading.Thread that runs the target synchronously, so
    tests can assert on the background-sent email without racing a real
    thread."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class JobLocationChoicesTests(TestCase):
    def test_location_field_only_allows_work_arrangement_choices(self):
        field = Job._meta.get_field('location')

        self.assertEqual(
            field.choices,
            [
                ('onsite', 'Onsite'),
                ('hybrid', 'Hybrid'),
                ('remote', 'Remote'),
            ],
        )

        job = Job(
            title='QA Engineer',
            department='Engineering',
            location='onsite',
            employment_type='full_time',
            description='Test role',
            requirements='Must be able to test',
        )
        job.full_clean()

        with self.assertRaises(ValidationError):
            invalid_job = Job(
                title='QA Engineer',
                department='Engineering',
                location='Berlin',
                employment_type='full_time',
                description='Test role',
                requirements='Must be able to test',
            )
            invalid_job.full_clean()


class JobDeadlineTests(TestCase):
    """A passed deadline should auto-close a job everywhere the public
    site checks openness, without ever touching the stored is_open flag —
    see JobQuerySet.open() / Job.is_currently_open."""

    def setUp(self):
        self.client = APIClient()
        today = timezone.localdate()

        self.open_no_deadline = Job.objects.create(
            title='Open Role, No Deadline',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='desc',
            requirements='reqs',
        )
        self.open_future_deadline = Job.objects.create(
            title='Open Role, Future Deadline',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='desc',
            requirements='reqs',
            deadline=today + timedelta(days=7),
        )
        self.deadline_passed = Job.objects.create(
            title='Deadline Passed Role',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='desc',
            requirements='reqs',
            deadline=today - timedelta(days=1),
        )
        self.manually_closed = Job.objects.create(
            title='Manually Closed Role',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='desc',
            requirements='reqs',
            is_open=False,
        )

    def test_is_currently_open_property(self):
        self.assertTrue(self.open_no_deadline.is_currently_open)
        self.assertTrue(self.open_future_deadline.is_currently_open)
        self.assertFalse(self.deadline_passed.is_currently_open)
        self.assertFalse(self.manually_closed.is_currently_open)

    def test_open_queryset_excludes_passed_deadline_and_manually_closed(self):
        open_titles = set(Job.objects.open().values_list('title', flat=True))

        self.assertIn(self.open_no_deadline.title, open_titles)
        self.assertIn(self.open_future_deadline.title, open_titles)
        self.assertNotIn(self.deadline_passed.title, open_titles)
        self.assertNotIn(self.manually_closed.title, open_titles)

    def test_job_list_api_excludes_jobs_past_deadline(self):
        response = self.client.get(reverse('job-list'))
        titles = {job['title'] for job in response.data}

        self.assertIn(self.open_no_deadline.title, titles)
        self.assertNotIn(self.deadline_passed.title, titles)
        self.assertNotIn(self.manually_closed.title, titles)

    def test_job_detail_api_404s_once_deadline_passes(self):
        response = self.client.get(
            reverse('job-detail', kwargs={'slug': self.deadline_passed.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_application_to_job_past_deadline_is_rejected(self):
        response = self.client.post(
            reverse('application-create'),
            {
                'job': self.deadline_passed.id,
                'full_name': 'Jane Doe',
                'email': 'jane@example.com',
                'phone': '+123456789',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_dashboard_open_jobs_stat_excludes_passed_deadline(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        staff_user = User.objects.create_user(
            username='staff', password='pw', is_staff=True
        )
        self.client.force_authenticate(user=staff_user)

        response = self.client.get(reverse('admin-stats'))

        # Only open_no_deadline and open_future_deadline should count.
        self.assertEqual(response.data['stats']['open_jobs'], 2)


class JobApplicationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.job = Job.objects.create(
            title='Backend Engineer',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='Build APIs',
            requirements='Python and Django',
        )

    def test_application_model_and_api_can_save_a_real_record(self):
        response = self.client.post(
            reverse('application-create'),
            {
                'job': self.job.id,
                'full_name': 'Jane Doe',
                'email': 'jane@example.com',
                'phone': '+123456789',
                'cover_letter': 'I would love to apply.',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(JobApplication.objects.count(), 1)
        self.assertEqual(JobApplication.objects.get().job, self.job)
        self.assertEqual(JobApplication.objects.get().full_name, 'Jane Doe')

    def test_job_creates_unique_slug_from_title(self):
        job = Job.objects.create(
            title='Senior Python Developer',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='Build backend features',
            requirements='Strong Python experience',
        )

        self.assertEqual(job.slug, 'senior-python-developer')
        self.assertTrue(Job.objects.filter(slug='senior-python-developer').exists())

    def _apply(self, **overrides):
        data = {
            'job': self.job.id,
            'full_name': 'Jane Doe',
            'email': 'jane@example.com',
            'phone': '+123456789',
            'cover_letter': 'I would love to apply.',
        }
        data.update(overrides)
        return self.client.post(reverse('application-create'), data, format='multipart')

    def test_honeypot_fakes_success_without_saving_or_emailing(self):
        response = self._apply(website='http://spam.example.com')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(JobApplication.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_application_for_same_job_and_email_is_rejected(self):
        first = self._apply()
        self.assertEqual(first.status_code, 201)

        second = self._apply(full_name='Jane D. Doe')

        self.assertEqual(second.status_code, 409)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_duplicate_response_includes_existing_applications_tracking_info(self):
        first = self._apply()
        existing_id = JobApplication.objects.get().id

        second = self._apply(full_name='Jane D. Doe')

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data['status'], 'new')
        self.assertEqual(second.data['status_display'], 'New')
        self.assertEqual(second.data['job_title'], self.job.title)
        self.assertEqual(second.data['job_slug'], self.job.slug)
        self.assertTrue(second.data['tracking_token'])

        # The recovered token must point at the ORIGINAL application, not
        # a new one — a duplicate attempt must never create a second row.
        recovered_id = signing.loads(second.data['tracking_token'], salt='application-access')
        self.assertEqual(recovered_id, existing_id)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_duplicate_response_reflects_admin_status_updates(self):
        self._apply()
        application = JobApplication.objects.get()
        application.status = 'interview'
        application.save(update_fields=['status'])

        second = self._apply(full_name='Jane D. Doe')

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data['status'], 'interview')
        self.assertEqual(second.data['status_display'], 'Interview')

    def test_duplicate_check_is_case_insensitive_on_email(self):
        self._apply(email='jane@example.com')
        second = self._apply(email='Jane@Example.com')

        self.assertEqual(second.status_code, 409)
        self.assertEqual(JobApplication.objects.count(), 1)

    def test_same_email_can_apply_to_a_different_job(self):
        other_job = Job.objects.create(
            title='Frontend Engineer',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='Build UIs',
            requirements='React experience',
        )

        first = self._apply()
        second = self._apply(job=other_job.id)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(JobApplication.objects.count(), 2)

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_application_confirmation_email_is_sent_with_withdraw_link(self):
        response = self._apply()
        self.assertEqual(response.status_code, 201)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['jane@example.com'])
        self.assertIn(self.job.title, sent.subject)
        self.assertIn('/career/withdraw/', sent.body)

    def test_response_includes_tracking_token_and_status(self):
        response = self._apply()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'new')
        self.assertEqual(response.data['status_display'], 'New')
        self.assertTrue(response.data['tracking_token'])

        application_id = signing.loads(response.data['tracking_token'], salt='application-access')
        self.assertEqual(application_id, JobApplication.objects.get().id)

    def test_status_endpoint_returns_current_status_for_valid_token(self):
        created = self._apply()
        token = created.data['tracking_token']

        response = self.client.get(reverse('application-status'), {'token': token})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'new')
        self.assertEqual(response.data['job_title'], self.job.title)
        self.assertEqual(response.data['job_slug'], self.job.slug)

    def test_status_endpoint_reflects_admin_updates(self):
        created = self._apply()
        token = created.data['tracking_token']

        application = JobApplication.objects.get()
        application.status = 'shortlisted'
        application.save(update_fields=['status'])

        response = self.client.get(reverse('application-status'), {'token': token})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'shortlisted')
        self.assertEqual(response.data['status_display'], 'Shortlisted')

    def test_status_endpoint_rejects_invalid_token(self):
        response = self.client.get(reverse('application-status'), {'token': 'not-a-real-token'})

        self.assertEqual(response.status_code, 404)


class ApplicationWithdrawalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.job = Job.objects.create(
            title='Backend Engineer',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='Build APIs',
            requirements='Python and Django',
        )
        self.application = JobApplication.objects.create(
            job=self.job,
            full_name='Jane Doe',
            email='jane@example.com',
            phone='+123456789',
        )
        self.token = signing.dumps(self.application.id, salt='application-access')

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_withdraw_link_marks_application_as_withdrawn_and_notifies(self):
        response = self.client.get(f'/career/withdraw/{self.token}/')

        self.assertEqual(response.status_code, 200)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'withdrawn')

        # One confirmation to the applicant, one quiet copy to staff.
        self.assertEqual(len(mail.outbox), 2)
        recipients = [set(m.to) for m in mail.outbox]
        self.assertIn({'jane@example.com'}, recipients)
        self.assertIn(
            {'sales@figbloom.org', 'humanresource@figbloom.org', 'operations@figbloom.org'},
            recipients,
        )

    def test_withdrawing_twice_shows_already_withdrawn_without_resending(self):
        self.application.status = 'withdrawn'
        self.application.save(update_fields=['status'])

        response = self.client.get(f'/career/withdraw/{self.token}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_withdraw_token_does_not_change_application(self):
        response = self.client.get('/career/withdraw/not-a-real-token/')

        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'new')


class ApplicationStatusChangeNotificationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.client = APIClient()
        self.job = Job.objects.create(
            title='Backend Engineer',
            department='Engineering',
            location='remote',
            employment_type='full_time',
            description='Build APIs',
            requirements='Python and Django',
        )
        self.application = JobApplication.objects.create(
            job=self.job,
            full_name='Jane Doe',
            email='jane@example.com',
            phone='+123456789',
        )

        User = get_user_model()
        staff_user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        self.client.force_authenticate(user=staff_user)

    def _patch_status(self, new_status):
        return self.client.patch(
            reverse('admin-applications-detail', kwargs={'pk': self.application.id}),
            {'status': new_status},
        )

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_status_change_sends_notification_email(self):
        response = self._patch_status('shortlisted')

        self.assertEqual(response.status_code, 200)
        # One to the applicant, one internal copy to the HR/ops/sales list.
        self.assertEqual(len(mail.outbox), 2)

        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['jane@example.com'])
        self.assertIn('Shortlisted', sent.subject)
        self.assertIn(self.job.title, sent.subject)
        self.assertIn('shortlisted', sent.body.lower())
        self.assertIn('/career/withdraw/', sent.alternatives[0][0])

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_status_change_notifies_hr_ops_and_sales(self):
        self._patch_status('shortlisted')

        staff_email = mail.outbox[1]
        self.assertEqual(
            set(staff_email.to),
            {'sales@figbloom.org', 'humanresource@figbloom.org', 'operations@figbloom.org'},
        )
        self.assertIn(self.application.full_name, staff_email.body)
        self.assertIn('New', staff_email.body)
        self.assertIn('Shortlisted', staff_email.body)

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_rejected_status_uses_gentler_full_message(self):
        self._patch_status('rejected')

        sent = mail.outbox[0]
        # Collapse whitespace/line breaks from the multi-line HTML template
        # so substring checks aren't sensitive to how the source wraps.
        html_content = ' '.join(sent.alternatives[0][0].split())

        self.assertIn('move forward with another candidate', sent.body)
        # The HTML version gets the fuller, softer wording — thanks for
        # applying, it's not a reflection of their potential, and an
        # invitation to apply again — not just a one-line status update.
        self.assertIn('thank you so much for the time', html_content.lower())
        self.assertIn("isn't a reflection of your talent", html_content)
        self.assertIn('apply again for future roles', html_content)

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_no_email_sent_when_status_is_unchanged(self):
        response = self.client.patch(
            reverse('admin-applications-detail', kwargs={'pk': self.application.id}),
            {'full_name': 'Jane D. Doe'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    @patch('careers.views.threading.Thread', _ImmediateThread)
    def test_re_patching_same_status_sends_no_further_email(self):
        self._patch_status('shortlisted')
        self.assertEqual(len(mail.outbox), 2)

        self._patch_status('shortlisted')
        self.assertEqual(len(mail.outbox), 2)
