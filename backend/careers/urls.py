from django.urls import path
from .views import (
    JobListView,
    JobDetailView,
    ApplicationCreateView,
    NewsletterSubscribeView,
)


urlpatterns = [
    path('jobs/', JobListView.as_view(), name='job-list'),
    path('jobs/<slug:slug>/', JobDetailView.as_view(), name='job-detail'),
    path('applications/', ApplicationCreateView.as_view(), name='application-create'),
    path('newsletter/subscribe/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
]