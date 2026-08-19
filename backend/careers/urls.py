from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    JobListView,
    JobDetailView,
    ApplicationCreateView,
    NewsletterSubscribeView,
    ContactCreateView,
    JobAdminViewSet,
    ApplicationAdminViewSet,
    NewsletterAdminViewSet, csrf_token, admin_application_detail
)

router = DefaultRouter()
router.register('admin/jobs', JobAdminViewSet, basename='admin-jobs')
router.register('admin/applications', ApplicationAdminViewSet, basename='admin-applications')
router.register('admin/newsletter', NewsletterAdminViewSet, basename='admin-newsletter')

urlpatterns = [
    path('jobs/', JobListView.as_view(), name='job-list'),
    path('jobs/<slug:slug>/', JobDetailView.as_view(), name='job-detail'),
    path('applications/', ApplicationCreateView.as_view(), name='application-create'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('contact/', ContactCreateView.as_view(), name='contact-create'),
    path('auth/csrf/', csrf_token, name='csrf-token'),
    path('admin-dashboard/application-detail', admin_application_detail,name='admin-application-detail'),
   
] + router.urls