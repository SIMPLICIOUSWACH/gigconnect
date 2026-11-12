from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from accounts.models import User

from .models import ClientProfile, FreelancerProfile
from .search import update_search_vector


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CLIENT:
        ClientProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.FREELANCER:
        FreelancerProfile.objects.get_or_create(user=instance)


# The search vector follows the profile, its skills and the person's name.

@receiver(post_save, sender=FreelancerProfile)
def profile_saved(sender, instance, **kwargs):
    update_search_vector(instance)


@receiver(m2m_changed, sender=FreelancerProfile.skills.through)
def profile_skills_changed(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear') and isinstance(instance, FreelancerProfile):
        update_search_vector(instance)


@receiver(post_save, sender=User)
def freelancer_renamed(sender, instance, created, **kwargs):
    if created or instance.role != User.Role.FREELANCER:
        return
    profile = FreelancerProfile.objects.filter(user=instance).select_related('user').first()
    if profile is not None:
        update_search_vector(profile)
