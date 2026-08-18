"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from careers.views import admin_subscribers
from careers.views import(admin_application_detail, admin_profile_settings,ChangePasswordView,)
from . import views
from careers.views import admin_subscribers
from careers.views import ChangePasswordView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('careers.urls')),

    # Admin dashboard (separate from Django's built-in /admin/)
    path('admin-dashboard/login', views.admin_login_page, name='admin-login-page'),
    path('api/auth/login/', views.admin_login_api, name='admin-login-api'),
    path('api/auth/logout/', views.admin_logout_api, name='admin-logout-api'),
    path('api/auth/user/', views.admin_user_api, name='admin-user-api'),
    path('admin-dashboard/', views.admin_dashboard_page, name='admin-dashboard'),
    path("admin-dashboard/subscribers",admin_subscribers,name="admin-subscribers"),
    path('', views.home, name='home'),
    # Each page answers on BOTH /x and /x/ with a 200 instead of redirecting between
    # them. A redirect in either direction keeps breaking links whenever one form
    # or the other gets normalised. The sitemap and rel=canonical advertise the
    # trailing-slash form, so that pattern carries the URL name and is what
    # reverse() returns; the bare pattern is an unnamed alias.
    path('about-us/', views.about_us, name='about-us'),
    path('about-us', views.about_us),
    path('career/', views.career, name='career'),
    path('career', views.career),
    path('career/detail/', views.job_detail_page, name='job-detail-page'),
    path('career/detail', views.job_detail_page),
    path('contact/', views.contact, name='contact'),
    path('contact', views.contact),
    path('projects/', views.projects, name='projects'),
    path('projects', views.projects),
    path('service/', views.service, name='service'),
    path('service', views.service),
    path('admin-dashboard/application-detail', admin_application_detail,name='admin-application-detail'),
    path("admin-dashboard/subscribers",admin_subscribers,name="admin-subscribers"),
    path("api/auth/change-password/",ChangePasswordView.as_view(),name="change-password"),
    path("admin-dashboard/profile-settings",admin_profile_settings,name="admin-profile-settings"),     
      
]

if settings.DEBUG:
    urlpatterns += static('/assets/', document_root=settings.BASE_DIR.parent / 'frontend' / 'assets')
    urlpatterns += static('/components/', document_root=settings.BASE_DIR.parent / 'frontend' / 'components')

# /assets/, /components/, robots.txt and sitemap.xml are served straight out of
# frontend/ by WhiteNoise (settings.WHITENOISE_ROOT) in both dev and production.

# Uploaded CVs only need a Django-served URL when object storage is not
# configured; with Cloudinary the storage backend returns absolute URLs.
if settings.DEBUG and not settings.USE_CLOUDINARY:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
