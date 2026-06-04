from django.contrib.auth.models import User


def get_usuarios_queryset():
    return (
        User.objects.select_related("profile")
        .prefetch_related("groups", "groups__meta", "user_permissions")
        .order_by("-id")
    )
