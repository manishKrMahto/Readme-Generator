from __future__ import annotations

import logging
from pathlib import Path

from django.db import IntegrityError
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.backend.ingestion_services import RepoIngestionService
from core.backend.models import Repository
from core.backend.processing_services import ProcessingPipelineService
from core.backend.readme_services import ReadmeComposerService
from core.backend.serializers import GenerateReadmeRequestSerializer
from core.backend.tasks import generate_readme_task
from core.backend.models import ReadmeGenerationMonitor

logger = logging.getLogger(__name__)


def readme_sections_payload(repo: Repository) -> dict:
    return {
        "readme": repo.readme_full,
        "readme_full": repo.readme_full,
        "readme_title": repo.readme_title,
        "readme_tagline": repo.readme_tagline,
        "readme_table_of_contents": repo.readme_table_of_contents,
        "readme_description": repo.readme_description,
        "readme_code_structure": repo.readme_code_structure,
        "readme_future_improvements": repo.readme_future_improvements,
        "readme_generated_at": repo.readme_generated_at,
    }


def readme_download_url(repo: Repository) -> str:
    return f"/api/repositories/{repo.id}/readme/download/"


def monitor_payload(repo: Repository) -> dict:
    """
    Best-effort snapshot of the latest generation monitor for the repository.
    Returned by status endpoints so the UI can render the generation monitor table.
    """
    latest = ReadmeGenerationMonitor.objects.filter(repository=repo).order_by("-created_at").first()
    if not latest:
        return {
            "monitor_id": "",
            "llm_calls": [],
            "llm_call_count": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": "0",
            # legacy keys used by existing UI
            "tokens_used": 0,
            "cost_estimate_usd": "0",
        }

    total_tokens = int(getattr(latest, "total_tokens", 0) or 0)
    total_cost_usd = str(getattr(latest, "total_cost_usd", "0") or "0")
    return {
        "monitor_id": str(getattr(latest, "id", "") or ""),
        "llm_calls": list(getattr(latest, "llm_calls", []) or []),
        "llm_call_count": int(getattr(latest, "llm_call_count", 0) or 0),
        "total_input_tokens": int(getattr(latest, "total_input_tokens", 0) or 0),
        "total_output_tokens": int(getattr(latest, "total_output_tokens", 0) or 0),
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        # legacy keys used by existing UI
        "tokens_used": total_tokens,
        "cost_estimate_usd": total_cost_usd,
    }


class GenerateReadmeAPIView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        ser = GenerateReadmeRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        repo_url = ser.validated_data["repo_url"]

        try:
            repo, _ = Repository.objects.get_or_create(repo_url=repo_url)
        except IntegrityError:
            repo = Repository.objects.get(repo_url=repo_url)

        repo.status = Repository.Status.PENDING
        repo.last_error = ""
        repo.save(update_fields=["status", "last_error", "updated_at"])

        try:
            task = generate_readme_task.delay(str(repo.id))
            logger.info("Enqueued job. repository=%s task_id=%s", repo.id, task.id)
            return Response(
                {"repository_id": str(repo.id), "status": repo.status, "task_id": task.id},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            logger.warning("Celery enqueue failed; running synchronously. repository=%s err=%s", repo.id, e)
            RepoIngestionService().run(repo)
            ProcessingPipelineService().run(repo)
            repo.refresh_from_db()
            ReadmeComposerService().compose(repo)
            repo.refresh_from_db()
            return Response(
                {
                    "repository_id": str(repo.id),
                    "status": repo.status,
                    "tech_stack": repo.tech_stack,
                    "download_url": readme_download_url(repo),
                    **monitor_payload(repo),
                    **readme_sections_payload(repo),
                },
                status=status.HTTP_200_OK,
            )


class RepositoryStatusAPIView(APIView):
    def get(self, request, repository_id: str):
        repo = Repository.objects.get(id=repository_id)
        out = {
            "repository_id": str(repo.id),
            "status": repo.status,
            "last_error": repo.last_error,
            "tech_stack": repo.tech_stack,
            "download_url": readme_download_url(repo),
            **monitor_payload(repo),
        }
        if repo.readme_full:
            out.update(readme_sections_payload(repo))
        return Response(out)


class RepositoryReadmeDownloadAPIView(APIView):
    def get(self, request, repository_id: str):
        repo = Repository.objects.get(id=repository_id)
        filename = "README.md"

        if repo.local_path:
            p = Path(repo.local_path) / filename
            if p.exists() and p.is_file():
                return FileResponse(
                    p.open("rb"),
                    as_attachment=True,
                    filename=filename,
                    content_type="text/markdown; charset=utf-8",
                )

        content = repo.readme_full or ""
        resp = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

