from __future__ import annotations

import logging
import time
from pathlib import Path

from django.conf import settings
from django.db import transaction

from core.backend.agents.component_aggregator import ComponentAggregator
from core.backend.agents.api_endpoints_agent import ApiEndpointsAgent
from core.backend.agents.existing_readme_merger_agent import ExistingReadmeMergerAgent
from core.backend.agents.file_structure_agent import FileStructureAgent
from core.backend.agents.future_improvements_agent import FutureImprovementsAgent
from core.backend.agents.installation_instructions_agent import InstallationInstructionsAgent
from core.backend.agents.project_description_agent import ProjectDescriptionAgent
from core.backend.agents.project_title_agent import ProjectTitleAgent
from core.backend.agents.readme_renderer import ReadmeRenderer
from core.backend.agents.table_of_contents_agent import TableOfContentsAgent
from core.backend.agents.tech_stack_detection_agent import TechStackDetectionAgent
from core.backend.agents.types import AgentContext, JsonDict
from core.backend.models import CodeChunk, FileMetadata, ReadmeGenerationMonitor, Repository
from core.backend.monitoring import finalize_monitoring
from core.backend.tree import build_tree, render_tree_box_drawing

logger = logging.getLogger(__name__)


class AgentsOrchestratorService:
    """
    Runs the Agents Layer and returns:
    - aggregated components dict (README-ready)
    - rendered markdown readme
    - token/cost totals
    """

    def _read_existing_readme(self, repo_root: Path) -> str | None:
        for name in ("README.md", "readme.md", "README"):
            p = repo_root / name
            if p.exists() and p.is_file():
                try:
                    return p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return None
        return None

    def _folder_paths(self, files: list[FileMetadata]) -> list[str]:
        out: set[str] = set()
        for f in files:
            p = (f.file_path or "").replace("\\", "/").strip("/")
            if "/" in p:
                out.add(p.rsplit("/", 1)[0])
        # include top-level dirs too
        top: set[str] = set()
        for d in out:
            top.add(d.split("/", 1)[0])
        return sorted(out | top)

    def _tree_text(self, files: list[FileMetadata]) -> str:
        tree = build_tree([f.file_path for f in files])
        return render_tree_box_drawing(tree)

    def run(self, repository: Repository) -> dict:
        if not repository.local_path:
            raise ValueError("Repository has no local_path; run ingestion first.")
        started_perf = time.perf_counter()
        repo_root = Path(repository.local_path)
        files = list(FileMetadata.objects.filter(repository=repository, is_selected=True).order_by("file_path"))
        chunks = list(CodeChunk.objects.filter(repository=repository).select_related("file").order_by("file__file_path"))

        model = getattr(settings, "OPENAI_MODEL", "") or ""
        monitor = ReadmeGenerationMonitor.objects.create(
            repository=repository,
            repo_url=repository.repo_url,
            model=model,
            status=ReadmeGenerationMonitor.Status.STARTED,
            total_files_processed=len(files),
            total_chunks_created=len(chunks),
        )

        ctx = AgentContext(
            repository=repository,
            monitor=monitor,
            repo_root=repo_root,
            files=files,
            chunks=chunks,
            folder_paths=self._folder_paths(files),
            tree_text=self._tree_text(files),
            existing_readme_text=self._read_existing_readme(repo_root),
        )

        outputs: JsonDict = {}
        try:
            # Agent execution order (per spec)
            agents = [
                ProjectTitleAgent(),
                TechStackDetectionAgent(),
                ExistingReadmeMergerAgent(),
                ProjectDescriptionAgent(),
                ApiEndpointsAgent(),
                FileStructureAgent(),
                InstallationInstructionsAgent(),
                FutureImprovementsAgent(),
                TableOfContentsAgent(),
            ]
            for a in agents:
                r = a.run(ctx)
                outputs[a.name] = r.output  # type: ignore[assignment]

            agg = ComponentAggregator().aggregate(outputs)

            # Merge with existing README sections (prefer human-written, avoid duplication).
            merge = outputs.get("existing_readme_merger") or {}
            kept = (merge.get("kept_sections") or {}) if isinstance(merge, dict) else {}
            if kept:
                # Prefer installation/usage/configuration if present.
                for k in ("Installation", "Setup", "Usage", "Configuration"):
                    if k in kept and kept[k].strip():
                        agg = agg.__class__(  # type: ignore[misc]
                            **{**agg.__dict__, "installation": kept[k].strip()}
                        )
                        break

            readme = ReadmeRenderer().render(agg)

            tech_stack = outputs.get("tech_stack_detection") if isinstance(outputs.get("tech_stack_detection"), dict) else {}
            finalize_monitoring(
                monitor_id=monitor.id,
                status=ReadmeGenerationMonitor.Status.COMPLETED,
                readme_content=readme,
                readme_sections=agg.to_dict(),
                detected_tech_stack=tech_stack,
                total_files_processed=len(files),
                total_chunks_created=len(chunks),
                error_message="",
                failed_step="",
                started_perf_counter=started_perf,
            )

            monitor.refresh_from_db()
            return {
                "components": agg.to_dict(),
                "readme": readme,
                "tokens_used": int(monitor.total_tokens or 0),
                "cost_estimate_usd": str(monitor.total_cost_usd or "0"),
                "monitor_id": str(monitor.id),
            }
        except Exception as e:
            logger.exception("AgentsOrchestratorService failed. repository=%s", repository.id)
            finalize_monitoring(
                monitor_id=monitor.id,
                status=ReadmeGenerationMonitor.Status.FAILED,
                readme_content="",
                readme_sections={},
                detected_tech_stack={},
                total_files_processed=len(files),
                total_chunks_created=len(chunks),
                error_message=str(e),
                failed_step="agents_orchestrator",
                started_perf_counter=started_perf,
            )
            raise

