from django.conf import settings


def session_timeout(request):
    """Expose timer configuration only to authenticated templates."""
    if not request.user.is_authenticated:
        return {}
    return {
        "session_timeout_seconds": settings.SESSION_TIMEOUT_SECONDS,
        "session_warning_seconds": min(120, settings.SESSION_TIMEOUT_SECONDS),
    }
