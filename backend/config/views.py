from django.shortcuts import render

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