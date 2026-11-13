from django.contrib import admin

from .models import Activity


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'activity_date', 'is_published', 'is_featured')
    list_filter = ('category', 'is_published', 'is_featured')
    search_fields = ('title', 'summary', 'location')
    date_hierarchy = 'activity_date'
