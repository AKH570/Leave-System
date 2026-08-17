from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


EXPIRED_MESSAGE = (
    "Your session has expired due to inactivity. Please log in again."
)


class SessionTimeoutMiddleware:
    """Expire authenticated sessions using a server-owned last-activity value."""

    LAST_ACTIVITY_KEY = "_last_activity"
    PUBLIC_URL_NAMES = {"login", "logout", "register"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timeout = settings.SESSION_TIMEOUT_SECONDS
        now = int(timezone.now().timestamp())
        last_activity = request.session.get(self.LAST_ACTIVITY_KEY)
        is_public = self._is_public_path(request.path)

        if request.user.is_authenticated:
            if last_activity is not None and now - int(last_activity) >= timeout:
                logout(request)
                messages.warning(request, EXPIRED_MESSAGE)
                return redirect(settings.LOGIN_URL)

            # A valid authenticated request resets both the explicit activity
            # marker and Django's session expiry, keeping server/client in sync.
            request.session[self.LAST_ACTIVITY_KEY] = now
            request.session.set_expiry(timeout)
        elif (
            not is_public
            and settings.SESSION_COOKIE_NAME in request.COOKIES
            and not request.session.get("_auth_user_id")
        ):
            # The session backend may have already deleted an expired row.
            logout(request)
            messages.warning(request, EXPIRED_MESSAGE)
            return redirect(settings.LOGIN_URL)

        response = self.get_response(request)
        if request.user.is_authenticated:
            # Do not let Back restore sensitive authenticated pages from cache.
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response

    @staticmethod
    def _is_public_path(path):
        public_paths = {
            reverse("accounts:login"),
            reverse("accounts:logout"),
            reverse("accounts:register"),
        }
        return (
            path in public_paths
            or path.startswith(settings.STATIC_URL)
            or path.startswith(settings.MEDIA_URL)
            or path.startswith("/admin/login/")
        )
