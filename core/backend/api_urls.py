from __future__ import annotations

from django.urls import path

from core.backend import api_views

urlpatterns = [
    path("generate-readme/", api_views.GenerateReadmeAPIView.as_view(), name="generate_readme"),
    path(
        "repositories/<uuid:repository_id>/status/",
        api_views.RepositoryStatusAPIView.as_view(),
        name="repository_status",
    ),
    path(
        "repositories/<uuid:repository_id>/readme/download/",
        api_views.RepositoryReadmeDownloadAPIView.as_view(),
        name="repository_readme_download",
    ),
]

