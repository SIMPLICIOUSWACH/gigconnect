from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import OTP, User


class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ['-created_at']
    list_display = ['email', 'full_name', 'role', 'is_email_verified', 'is_phone_verified', 'is_active']
    list_filter = ['role', 'is_email_verified', 'is_phone_verified', 'is_active']
    search_fields = ['email', 'full_name', 'phone']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'phone', 'role')}),
        ('Status', {
            'fields': (
                'is_email_verified', 'is_phone_verified', 'is_profile_complete',
                'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions',
            )
        }),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ['created_at']


admin.site.register(User, UserAdmin)
admin.site.register(OTP)
