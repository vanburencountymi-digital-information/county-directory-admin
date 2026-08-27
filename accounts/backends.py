from django.contrib.auth.backends import BaseBackend
from django.utils import timezone

from .models import MagicLinkToken, User


class MagicLinkBackend(BaseBackend):
    """Authenticate via a one-time token emailed to a directory User."""

    def authenticate(self, request, token=None, **kwargs):
        if not token:
            return None
        try:
            record = MagicLinkToken.objects.select_related("user").get(token=token)
        except MagicLinkToken.DoesNotExist:
            return None
        if record.used_at is not None:
            return None
        if record.expires_at < timezone.now():
            return None
        if not record.user.is_active:
            return None
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        return record.user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
