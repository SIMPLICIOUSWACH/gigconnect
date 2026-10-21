from django.contrib import admin

from .models import RecommenderModelVersion


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
