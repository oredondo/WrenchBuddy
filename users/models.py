from django.contrib.auth.models import AbstractUser
from django.db import models


def avatar_path(instance, filename):
    return f'avatars/user_{instance.pk}/{filename}'


class CustomUser(AbstractUser):
    """Custom user model for WrenchBuddy."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    display_name  = models.CharField(max_length=100, blank=True)
    bio           = models.TextField(blank=True)
    location      = models.CharField(max_length=100, blank=True)
    avatar        = models.ImageField(upload_to=avatar_path, null=True, blank=True)
    show_spending = models.BooleanField(default=False)

    class LanguageChoices(models.TextChoices):
        SPANISH = 'es', 'Español'
        ENGLISH = 'en', 'English'

    preferred_language = models.CharField(
        max_length=5,
        choices=LanguageChoices.choices,
        default=LanguageChoices.SPANISH,
        help_text="User's preferred language for AI responses and interface."
    )


    class Meta:
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.email
