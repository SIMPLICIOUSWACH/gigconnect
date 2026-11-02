from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's own admin site, for debugging by a superuser. The product's admin area is /api/admin/ below.
    path('admin/', admin.site.urls),
    path('api/admin/', include('adminpanel.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('profiles.urls')),
    path('api/', include('usersettings.urls')),
    path('api/', include('gigs.urls')),
    path('api/', include('applications.urls')),
    path('api/', include('recommendations.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
