from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Gig


def update_search_vector(gig):
    """Recompute and persist the weighted search vector for one gig.

    Uses a queryset .update() (not .save()) so this never re-triggers post_save and loop.
    Skill names have to be pulled into a plain string first since SearchVector can't span an
    M2M join directly without duplicating rows per related skill.
    """
    skill_names = ' '.join(gig.skills.values_list('name', flat=True))
    vector = (
        SearchVector('title', weight='A')
        + SearchVector(Value(skill_names), weight='B')
        + SearchVector('description', weight='C')
    )
    Gig.objects.filter(pk=gig.pk).update(search_vector=vector)


@receiver(post_save, sender=Gig)
def gig_saved(sender, instance, **kwargs):
    update_search_vector(instance)


@receiver(m2m_changed, sender=Gig.skills.through)
def gig_skills_changed(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        update_search_vector(instance)
