from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'show_on_home', 'sort_order')
    list_filter = ('category', 'is_published', 'show_on_home')
    search_fields = ('title', 'category', 'description')
