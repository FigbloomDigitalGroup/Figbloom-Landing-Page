from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@ensure_csrf_cookie
def job_detail_page(request):
    return render(request, 'career/detail.html')

def home(request):
    return render(request, 'index.html')

def about_us(request):
    return render(request, 'about-us/index.html')

def career(request):
    return render(request, 'career/index.html')

def contact(request):
    return render(request, 'contact/index.html')

def projects(request):
    return render(request, 'projects/index.html')

def service(request):
    return render(request, 'service/index.html')


# --- Admin dashboard auth + pages ---

@ensure_csrf_cookie
def admin_login_page(request):
    return render(request, 'admin-dashboard/login.html')


def admin_login_api(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    username = request.POST.get('username')
    password = request.POST.get('password')
    user = authenticate(request, username=username, password=password)

    if user is not None and user.is_staff:
        login(request, user)
        return JsonResponse({'message': 'Logged in'})
    return JsonResponse({'detail': 'Invalid credentials'}, status=401)


def admin_logout_api(request):
    logout(request)
    return JsonResponse({'message': 'Logged out'})


@login_required(login_url='/admin-dashboard/login')
def admin_dashboard_page(request):
    return render(request, 'admin-dashboard/index.html')


@ensure_csrf_cookie
def admin_user_api(request):
    """Return basic info about the current session user for front-end visibility checks."""
    user = getattr(request, 'user', None)
    is_auth = bool(user and user.is_authenticated)
    return JsonResponse({
        'is_authenticated': is_auth,
        'is_staff': user.is_staff if is_auth else False,
        'username': user.username if is_auth else '',
    })