from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    JobListView,
    JobDetailView,
    ApplicationCreateView,
    ApplicationStatusView,
    NewsletterSubscribeView,
    ContactCreateView,
    JobAdminViewSet,
    ApplicationAdminViewSet,
    NewsletterAdminViewSet,
    ContactAdminViewSet,
    SentNewsletterAdminViewSet,
    DashboardStatsView, csrf_token,
    newsletter_unlock_view,
)

router = DefaultRouter()
router.register('admin/jobs', JobAdminViewSet, basename='admin-jobs')
router.register('admin/applications', ApplicationAdminViewSet, basename='admin-applications')
router.register('admin/newsletter', NewsletterAdminViewSet, basename='admin-newsletter')
router.register('admin/contact', ContactAdminViewSet, basename='admin-contact')
router.register('admin/newsletter-history', SentNewsletterAdminViewSet, basename='admin-newsletter-history')

urlpatterns = [
    path('jobs/', JobListView.as_view(), name='job-list'),
    path('jobs/<slug:slug>/', JobDetailView.as_view(), name='job-detail'),
    path('applications/', ApplicationCreateView.as_view(), name='application-create'),
    path('applications/status/', ApplicationStatusView.as_view(), name='application-status'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('newsletters/<slug:slug>/unlock/', newsletter_unlock_view, name='newsletter-unlock'),
    path('contact/', ContactCreateView.as_view(), name='contact-create'),
    path('auth/csrf/', csrf_token, name='csrf-token'),
    path('admin/stats/', DashboardStatsView.as_view(), name='admin-stats'),
] + router.urls