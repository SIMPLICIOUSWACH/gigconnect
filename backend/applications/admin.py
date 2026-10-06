from django.contrib import admin

from .models import Application, ApplicationStatusEvent


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('gig', 'freelancer', 'status', 'is_synthetic', 'created_at')
    list_filter = ('status', 'is_synthetic')
    search_fields = ('gig__title', 'freelancer__email', 'freelancer__full_name')
    raw_id_fields = ('gig', 'freelancer')


@admin.register(ApplicationStatusEvent)
class ApplicationStatusEventAdmin(admin.ModelAdmin):
    list_display = ('application', 'from_status', 'to_status', 'changed_by', 'created_at')
    list_filter = ('to_status',)
    raw_id_fields = ('application', 'changed_by')
