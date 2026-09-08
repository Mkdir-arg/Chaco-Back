from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance)
        instance._state.fields_cache["profile"] = profile


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # No consultar la relación en cada User.save(): además de ser innecesario,
    # produciría un N+1 en procesos que actualizan usuarios en lote.
    profile = instance._state.fields_cache.get("profile")
    if profile is not None:
        profile.save()
