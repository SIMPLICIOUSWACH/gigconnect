from django.db import models


class SampleRecord(models.Model):
    """
    What enrich_sample_data and seed_showcase did, so --undo can take back exactly that and nothing else.

    CREATED: a row the command made (a gig, a user, a portfolio item, a notification). Deleting it takes its
    applications, reviews, chats and so on with it.
    CHANGED: a field of an existing row the command filled in. `old_value` is what it held before, so undo can put it
    back (and delete a generated image that was saved into it).
    DONE: a marker that one step is finished for one row, so running a command again skips it.
    ANCHOR: the day the dates were last set, which refresh_showcase_dates moves forward from.
    """

    class Batch(models.TextChoices):
        ENRICH = 'enrich', 'Enrich sample data'
        SHOWCASE = 'showcase', 'Showcase accounts'

    class Kind(models.TextChoices):
        CREATED = 'created', 'Created'
        CHANGED = 'changed', 'Changed'
        DONE = 'done', 'Done'
        ANCHOR = 'anchor', 'Anchor'

    batch = models.CharField(max_length=20, choices=Batch.choices)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # "app_label.ModelName" of the row this is about, and its primary key as text.
    model_label = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=40, blank=True)
    # The field that changed, or the step that is done.
    field = models.CharField(max_length=60, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'kind', 'model_label', 'object_id', 'field'], name='one_sample_record_per_thing',
            ),
        ]
        indexes = [models.Index(fields=['batch', 'kind', 'model_label'], name='samplerecord_lookup_idx')]

    def __str__(self):
        return f'{self.batch} {self.kind} {self.model_label} {self.object_id} {self.field}'.strip()
