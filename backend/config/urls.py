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

from careers.views import admin_application_detail
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('careers.urls')),

    # Admin dashboard (separate from Django's built-in /admin/)
    path('admin-dashboard/login', views.admin_login_page, name='admin-login-page'),
    path('api/auth/login/', views.admin_login_api, name='admin-login-api'),
    path('api/auth/logout/', views.admin_logout_api, name='admin-logout-api'),
    path('api/auth/user/', views.admin_user_api, name='admin-user-api'),
    path('admin-dashboard/', views.admin_dashboard_page, name='admin-dashboard'),

    path('', views.home, name='home'),
    path('about-us', views.about_us, name='about-us'),
    path('career', views.career, name='career'),
    path('career/detail', views.job_detail_page, name='job-detail-page'),
    path('contact', views.contact, name='contact'),
    path('projects', views.projects, name='projects'),
    path('service', views.service, name='service'),
    path('admin-dashboard/application-detail', admin_application_detail,name='admin-application-detail'
),
]

if settings.DEBUG:
    urlpatterns += static('/assets/', document_root=settings.BASE_DIR.parent / 'frontend' / 'assets')
    urlpatterns += static('/components/', document_root=settings.BASE_DIR.parent / 'frontend' / 'components')
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)