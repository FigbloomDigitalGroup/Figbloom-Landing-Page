from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Job, JobApplication


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
