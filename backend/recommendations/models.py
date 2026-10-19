import uuid

from django.db import models


class RecommenderModelVersion(models.Model):
    """
    One training run. The newest row is the model in use.

    The trained files live in the artefacts folder (settings.RECOMMENDER_ARTIFACT_DIR), in a folder named
    by `folder`. This row is written last, after the files are safely in place, so a loader that finds a
    row can rely on the files being there. It records what the model was trained on, so any score can be
    traced back to its data, including how much of it was synthetic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(unique=True)
    folder = models.CharField(max_length=100)
    trained_at = models.DateTimeField(auto_now_add=True)

    include_synthetic = models.BooleanField()
    # The content model: gigs on the platform, and the external job postings it was also fitted on.
    platform_gigs = models.PositiveIntegerField()
    synthetic_platform_gigs = models.PositiveIntegerField()
    external_documents = models.PositiveIntegerField()
    vocabulary_size = models.PositiveIntegerField()
    freelancers = models.PositiveIntegerField()

    # The collaborative model, or why there isn't one.
    collaborative_fitted = models.BooleanField()
    collaborative_skipped_reason = models.CharField(max_length=300, blank=True)
    interactions = models.PositiveIntegerField(help_text='Freelancer and gig pairs in the matrix.')
    synthetic_interactions = models.PositiveIntegerField()
    collaborative_scale = models.FloatField(
        null=True, blank=True, help_text='Raw collaborative score that maps to 1.0, from this training run.',
    )

    parameters = models.JSONField(default=dict)

    class Meta:
        ordering = ['-version']

    @property
    def synthetic_gig_share(self):
        return self.synthetic_platform_gigs / self.platform_gigs if self.platform_gigs else 0.0

    @property
    def synthetic_interaction_share(self):
        return self.synthetic_interactions / self.interactions if self.interactions else 0.0

    def __str__(self):
        return f'Recommender v{self.version} ({self.trained_at:%Y-%m-%d})'
