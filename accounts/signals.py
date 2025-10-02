# accounts/signals.py
# 🔔 Create a default UserProfile automatically for each new User.

from django.db.models.signals import post_save                     # ✅ listen for saves
from django.dispatch import receiver                               # ✅ decorator helper
from django.contrib.auth import get_user_model                     # ✅ safe user model access
from .models import UserProfile                                    # ✅ the profile we create

User = get_user_model()                                            # ✅ resolves to AUTH_USER_MODEL

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # 🍼 when a new user is saved for the first time, create a matching profile
    if created:
        UserProfile.objects.get_or_create(user=instance)           # currency defaults to "GBP"
