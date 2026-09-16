from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User

from .models import ClientProfile, FreelancerProfile


@receiver(post_save, sender=User)
def create_profile_for_user(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CLIENT:
        ClientProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.FREELANCER:
        FreelancerProfile.objects.get_or_create(user=instance)
