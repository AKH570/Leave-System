from django.apps import AppConfig


class AttendancesConfig(AppConfig):
    name = 'attendances'

    def ready(self):
        # Register authentication event handlers when Django starts.
        from . import signals  # noqa: F401
