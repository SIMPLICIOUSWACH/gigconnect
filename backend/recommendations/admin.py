from django.conf import settings
from django.contrib import admin

from .evaluation.modes import profile_text
from .models import RecommenderModelVersion

# Every admin page says which recommender profile is running, and the demo one says it is planted data.
_PROFILE = profile_text(settings.RECOMMENDER_PROFILE, settings.RECOMMENDER_PROFILE_LABEL)
admin.site.site_header = f'GigConnect admin ({_PROFILE})'
admin.site.index_title = f'Recommender profile: {_PROFILE}'


@admin.register(RecommenderModelVersion)
class RecommenderModelVersionAdmin(admin.ModelAdmin):
    list_display = (
        'version', 'trained_at', 'platform_gigs', 'external_documents', 'freelancers', 'interactions',
        'collaborative_fitted', 'include_synthetic',
    )
    list_filter = ('collaborative_fitted', 'include_synthetic')
    # A training run is a record. It is made by the train_recommender command, never edited by hand.
    readonly_fields = [field.name for field in RecommenderModelVersion._meta.fields]

    def has_add_permission(self, request):
        return False
