from __future__ import annotations

from django.urls import path

from core.backend import views

urlpatterns = [
    path("", views.FrontendView.as_view(), name="home"),
]

