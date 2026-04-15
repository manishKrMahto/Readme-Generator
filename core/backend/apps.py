from __future__ import annotations

from django.apps import AppConfig


class CoreBackendConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.backend"
    label = "core_backend"

