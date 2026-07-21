"""Reset application data while retaining Django's required system records.

Interactive use::

    python manage.py reset_uat_data

Automation (confirmation is bypassed)::

    python manage.py reset_uat_data --no-input

Uploaded files are preserved unless ``--delete-media`` is also supplied.
"""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.models import Model
from django.db.models.deletion import DO_NOTHING, SET_DEFAULT, SET_NULL


WARNING = (
    "This will permanently delete all UAT application data.\n"
    "Type RESET to continue: "
)


class Command(BaseCommand):
    help = (
        "Delete all project application data, preserve superusers and Django "
        "system data, and reset database sequences."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Run without the interactive RESET confirmation.",
        )
        parser.add_argument(
            "--delete-media",
            action="store_true",
            help="Also delete files and directories inside MEDIA_ROOT.",
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help="Database to reset (default: default).",
        )

    def handle(self, *args, **options):
        if not options["no_input"]:
            self.stderr.write(self.style.WARNING(WARNING.splitlines()[0]))
            if input(WARNING.splitlines()[1]) != "RESET":
                self.stdout.write(self.style.WARNING("Reset cancelled; no data was deleted."))
                return

        database = options["database"]
        connection = connections[database]
        user_model = get_user_model()
        application_models = self._application_models()
        deletion_models = [model for model in application_models if model is not user_model]
        deletion_order = self._deletion_order(deletion_models)
        deleted_counts: dict[type[Model], int] = {}

        try:
            # All database work, including sequence resets, succeeds or rolls back together.
            with transaction.atomic(using=database):
                for model in deletion_order:
                    queryset = model._default_manager.using(database).all()
                    deleted_counts[model] = queryset.count()
                    queryset.delete()

                non_superusers = user_model._default_manager.using(database).filter(
                    is_superuser=False,
                )
                deleted_counts[user_model] = non_superusers.count()
                non_superusers.delete()

                self._reset_sequences(connection, deletion_models, user_model)
        except Exception as exc:
            raise CommandError(
                f"UAT reset failed; all database changes were rolled back: {exc}"
            ) from exc

        self._write_summary(deleted_counts, user_model, database)

        # Files cannot participate in a database transaction, so they are removed only
        # after the database cleanup has committed successfully.
        if options["delete_media"]:
            self._delete_media()
        else:
            self.stdout.write("Uploaded media: preserved (use --delete-media to remove it)")

        self.stdout.write(self.style.SUCCESS("UAT data reset completed successfully."))

    @staticmethod
    def _application_models() -> list[type[Model]]:
        """Return concrete models owned by this project, not django.contrib."""
        models = []
        for model in apps.get_models(include_auto_created=False):
            if model._meta.proxy or not model._meta.managed:
                continue
            if model._meta.app_config.name.startswith("django.contrib."):
                continue
            models.append(model)
        return sorted(models, key=lambda item: item._meta.label_lower)

    @staticmethod
    def _deletion_order(models: list[type[Model]]) -> list[type[Model]]:
        """Order dependent rows before referenced rows to satisfy FK constraints."""
        model_set = set(models)
        edges: dict[type[Model], set[type[Model]]] = defaultdict(set)
        indegree = {model: 0 for model in models}

        for model in models:
            for field in model._meta.fields:
                remote = getattr(field, "remote_field", None)
                target = getattr(remote, "model", None)
                on_delete = getattr(remote, "on_delete", None)
                if (
                    target in model_set
                    and target is not model
                    and on_delete not in {SET_NULL, SET_DEFAULT, DO_NOTHING}
                    and target not in edges[model]
                ):
                    edges[model].add(target)
                    indegree[target] += 1

        ready = sorted(
            (model for model, degree in indegree.items() if degree == 0),
            key=lambda item: item._meta.label_lower,
        )
        ordered = []
        while ready:
            model = ready.pop(0)
            ordered.append(model)
            for target in sorted(edges[model], key=lambda item: item._meta.label_lower):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=lambda item: item._meta.label_lower)

        # Any remaining cycle can only be resolved by ORM cascading/database behavior.
        ordered.extend(sorted(set(models) - set(ordered), key=lambda item: item._meta.label_lower))
        return ordered

    @staticmethod
    def _reset_sequences(
        connection,
        empty_models: list[type[Model]],
        user_model: type[Model],
    ) -> None:
        # Empty tables can safely restart at their initial value. The user table
        # still contains superusers, so its next value must follow its highest PK.
        sequences = [
            {"table": model._meta.db_table, "column": model._meta.pk.column}
            for model in empty_models
        ]
        sql = connection.ops.sequence_reset_by_name_sql(no_style(), sequences)
        sql.extend(connection.ops.sequence_reset_sql(no_style(), [user_model]))
        with connection.cursor() as cursor:
            for statement in sql:
                cursor.execute(statement)

    def _write_summary(self, counts, user_model, database):
        self.stdout.write("\nDeletion summary")
        self.stdout.write("----------------")
        for model in sorted(counts, key=lambda item: item._meta.label_lower):
            self.stdout.write(f"{model._meta.label}: {counts[model]} deleted")

        superuser_count = user_model._default_manager.using(database).filter(
            is_superuser=True,
        ).count()
        self.stdout.write("\nPreserved/skipped models")
        self.stdout.write("------------------------")
        self.stdout.write(f"{user_model._meta.label}: {superuser_count} superuser(s) preserved")
        for model in sorted(
            (
                model for model in apps.get_models(include_auto_created=False)
                if model._meta.app_config.name.startswith("django.contrib.")
            ),
            key=lambda item: item._meta.label_lower,
        ):
            self.stdout.write(f"{model._meta.label}: skipped (Django system model)")

    def _delete_media(self):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if not media_root.exists():
            self.stdout.write("Uploaded media: MEDIA_ROOT does not exist; nothing deleted")
            return
        if not media_root.is_dir() or media_root == media_root.parent:
            raise CommandError(f"Refusing unsafe MEDIA_ROOT: {media_root}")

        try:
            for child in media_root.iterdir():
                if child.is_symlink() or child.is_file():
                    child.unlink()
                elif child.is_dir():
                    shutil.rmtree(child)
        except OSError as exc:
            raise CommandError(
                "Database cleanup completed, but uploaded media deletion failed: "
                f"{exc}"
            ) from exc
        self.stdout.write(self.style.SUCCESS(f"Uploaded media deleted from {media_root}"))
