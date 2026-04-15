from __future__ import annotations

import logging

from celery import shared_task

from core.backend.ingestion_services import RepoIngestionService
from core.backend.models import Repository
from core.backend.processing_services import ProcessingPipelineService
from core.backend.readme_services import ReadmeComposerService
from core.backend.models import ReadmeGenerationMonitor

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def generate_readme_task(self, repository_id: str) -> dict:
    repo = Repository.objects.get(id=repository_id)
    logger.info("Job started. repository=%s", repo.id)

    RepoIngestionService().run(repo)
    ProcessingPipelineService().run(repo)

    repo.refresh_from_db()
    ReadmeComposerService().compose(repo)
    repo.refresh_from_db()

    repo.status = Repository.Status.COMPLETED
    repo.last_error = ""
    repo.save(update_fields=["status", "last_error", "updated_at"])

    logger.info("Job completed. repository=%s", repo.id)
    latest = ReadmeGenerationMonitor.objects.filter(repository=repo).order_by("-created_at").first()
    return {
        "repository_id": str(repo.id),
        "tech_stack": repo.tech_stack,
        "readme": repo.readme_full,
        "readme_full": repo.readme_full,
        "readme_title": repo.readme_title,
        "readme_tagline": repo.readme_tagline,
        "readme_table_of_contents": repo.readme_table_of_contents,
        "readme_description": repo.readme_description,
        "readme_code_structure": repo.readme_code_structure,
        "readme_future_improvements": repo.readme_future_improvements,
        "readme_generated_at": repo.readme_generated_at.isoformat() if repo.readme_generated_at else None,
        "tokens_used": int(getattr(latest, "total_tokens", 0) or 0),
        "cost_estimate_usd": str(getattr(latest, "total_cost_usd", "0") or "0"),
        "monitor_id": str(getattr(latest, "id", "") or ""),
    }

