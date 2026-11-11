from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    """Log in with either the username or the email address (web pages and API)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        username = username.strip()
        user = User.objects.filter(username__iexact=username).first()
        if user is None and "@" in username:
            user = User.objects.filter(email__iexact=username).order_by("pk").first()
        if user is None:
            User().set_password(password)  # same timing as a real check
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
