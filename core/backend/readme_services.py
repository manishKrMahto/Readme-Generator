from __future__ import annotations

from pathlib import Path

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.backend.folder_comments import folder_comment_for_path
from core.backend.models import FileMetadata, Repository
from core.backend.agents.orchestrator import AgentsOrchestratorService
from core.backend.tree import (
    build_tree,
    filter_paths_excluding_large_subtrees,
    iter_directory_paths_from_tree,
    render_tree_box_drawing,
)

logger = logging.getLogger(__name__)


class ReadmeComposerService:
    def compose(self, repository: Repository) -> str:
        # New Agents Layer (runs before rendering final README).
        # Falls back to legacy composer if anything goes wrong.
        try:
            result = AgentsOrchestratorService().run(repository)
            components = result.get("components") or {}
            readme_full = result.get("readme") or ""

            title = str(components.get("title") or "").strip()
            toc = str(components.get("table_of_contents") or "").strip()
            description = str(components.get("description") or "").strip()
            future_improvements = str(components.get("future_improvements") or "").strip()

            # Preserve legacy fields for UI compatibility.
            repository.readme_title = title
            repository.readme_tagline = ""  # tagline now lives inside description; keep blank
            repository.readme_table_of_contents = toc
            repository.readme_description = description
            repository.readme_code_structure = str(components.get("file_structure") or "").strip()
            repository.readme_future_improvements = future_improvements
            repository.readme_full = readme_full
            repository.save(
                update_fields=[
                    "readme_title",
                    "readme_tagline",
                    "readme_table_of_contents",
                    "readme_description",
                    "readme_code_structure",
                    "readme_future_improvements",
                    "readme_full",
                    "updated_at",
                ]
            )

            try:
                if repository.local_path:
                    repo_root = Path(repository.local_path)
                    repo_root.mkdir(parents=True, exist_ok=True)
                    (repo_root / "README.md").write_text(readme_full, encoding="utf-8")
            except Exception:
                pass

            return readme_full
        except Exception as e:
            # Not silent: ensure failure is visible in logs.
            logger.exception("Agents layer failed; using legacy composer. repository=%s err=%s", repository.id, e)

        selected_files = list(
            FileMetadata.objects.filter(repository=repository, is_selected=True).order_by("file_path")
        )
        large_threshold = int(getattr(settings, "README_TREE_LARGE_FILE_BYTES", 512 * 1024))

        paths_with_sizes = [(f.file_path, int(f.size_bytes)) for f in selected_files]
        tree_paths = filter_paths_excluding_large_subtrees(paths_with_sizes, large_threshold)
        tree = build_tree(tree_paths)
        box_tree = render_tree_box_drawing(tree)

        dir_paths = iter_directory_paths_from_tree(tree)
        folder_lines = [
            f"- **`{d}/`** — {folder_comment_for_path(d, repository.tech_stack or Repository.TechStack.UNKNOWN)}"
            for d in dir_paths
        ]
        folder_notes = "\n".join(folder_lines) if folder_lines else "- *(No subdirectories in this tree.)*"

        code_structure_body = "\n".join(
            [
                "Directory layout. **Subfolders were omitted** if they *directly* contained a file "
                f"larger than **{large_threshold // 1024} KB** (configurable via `README_TREE_LARGE_FILE_BYTES`).",
                "",
                "```text",
                box_tree or "(empty)",
                "```",
                "",
                "### Folder notes",
                "",
                folder_notes,
            ]
        )

        title = repository.repo_url.rstrip("/").split("/")[-1] or "Project"
        tagline = f"{title} — {repository.get_tech_stack_display()} project (inferred from repository layout)."
        description = "Project overview derived from repository structure."

        toc = "\n".join(
            [
                "- [Description](#description)",
                "- [Code structure](#code-structure)",
                "- [Future improvements](#future-improvements)",
            ]
        )

        future_improvements = "\n".join(
            [
                "- Refine tech-stack detection with more repository signals.",
                "- Add richer README sections (installation, usage) once stack is certain.",
                "- Expand automated tests and CI for the main languages in the repo.",
            ]
        )

        readme_full = "\n".join(
            [
                f"# {title}",
                "",
                tagline,
                "",
                "## Table of contents",
                "",
                toc,
                "",
                "## Description",
                "",
                description,
                "",
                "## Code structure",
                "",
                code_structure_body,
                "",
                "## Future improvements",
                "",
                future_improvements,
            ]
        )

        with transaction.atomic():
            repository.refresh_from_db()
            repository.readme_title = title
            repository.readme_tagline = tagline
            repository.readme_table_of_contents = toc
            repository.readme_description = description
            repository.readme_code_structure = code_structure_body
            repository.readme_future_improvements = future_improvements
            repository.readme_full = readme_full
            repository.readme_generated_at = timezone.now()
            repository.save(
                update_fields=[
                    "readme_title",
                    "readme_tagline",
                    "readme_table_of_contents",
                    "readme_description",
                    "readme_code_structure",
                    "readme_future_improvements",
                    "readme_full",
                    "readme_generated_at",
                    "updated_at",
                ]
            )

        try:
            if repository.local_path:
                repo_root = Path(repository.local_path)
                repo_root.mkdir(parents=True, exist_ok=True)
                (repo_root / "README.md").write_text(readme_full, encoding="utf-8")
        except Exception:
            pass

        return readme_full

