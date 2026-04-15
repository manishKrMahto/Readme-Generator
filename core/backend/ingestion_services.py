from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.db import transaction
from git import Repo
from git.exc import GitCommandError

from core.backend.models import FileMetadata, Repository
from core.backend.selection import StackAwareFileSelectorService
from core.backend.tech_stack import TechStackDetectorService
from core.backend.tree import build_tree, render_tree_box_drawing
from core.backend.utils import (
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_EXCLUDED_DIRS,
    is_binary_file,
    safe_relpath,
    should_exclude_dir,
)

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    pass


class InvalidRepositoryUrl(IngestionError):
    pass


class RepositoryCloneFailed(IngestionError):
    pass


@dataclass(frozen=True)
class FileFilterConfig:
    excluded_dirs: set[str] = None  # type: ignore[assignment]
    allowed_extensions: set[str] = None  # type: ignore[assignment]
    max_file_size_bytes: int = 2 * 1024 * 1024  # 2MB

    def __post_init__(self) -> None:
        object.__setattr__(self, "excluded_dirs", self.excluded_dirs or set(DEFAULT_EXCLUDED_DIRS))
        object.__setattr__(
            self, "allowed_extensions", self.allowed_extensions or set(DEFAULT_ALLOWED_EXTENSIONS)
        )


class RepoClonerService:
    def clone(self, repository: Repository) -> Path:
        repo_url = (repository.repo_url or "").strip()
        if not (
            repo_url.startswith("https://")
            or repo_url.startswith("http://")
            or repo_url.startswith("git@")
        ):
            raise InvalidRepositoryUrl(f"Unsupported repo URL: {repo_url}")

        workdir = Path(getattr(settings, "REPO_WORKDIR", settings.BASE_DIR / "var" / "repos"))
        workdir.mkdir(parents=True, exist_ok=True)

        repo_dir = workdir / str(repository.id)
        repo_dir.mkdir(parents=True, exist_ok=True)
        target_dir = repo_dir / uuid.uuid4().hex

        if repository.local_path:
            try:
                shutil.rmtree(repository.local_path, ignore_errors=True)
            except Exception:
                pass

        logger.info("Cloning repository. repo_url=%s target_dir=%s", repo_url, target_dir)
        try:
            Repo.clone_from(repo_url, str(target_dir))
        except GitCommandError as e:
            raise RepositoryCloneFailed(str(e)) from e

        repository.local_path = str(target_dir)
        repository.status = Repository.Status.CLONING
        repository.last_error = ""
        repository.save(update_fields=["local_path", "status", "last_error", "updated_at"])

        return target_dir


class FileFilterService:
    def __init__(self, config: FileFilterConfig | None = None) -> None:
        self.config = config or FileFilterConfig()

    def iter_relevant_files(self, repo_root: Path) -> list[Path]:
        kept: list[Path] = []
        for path in repo_root.rglob("*"):
            if path.is_dir():
                if should_exclude_dir(path.name, self.config.excluded_dirs):
                    continue
                continue

            parts = set(path.parts)
            if parts & self.config.excluded_dirs:
                continue

            if not path.exists():
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue

            if size <= 0 or size > self.config.max_file_size_bytes:
                continue

            suffix = path.suffix.lower()
            if suffix and suffix not in self.config.allowed_extensions:
                name_lower = path.name.lower()
                if name_lower not in {"dockerfile", "makefile", "license", "readme"}:
                    continue

            if is_binary_file(path):
                continue

            kept.append(path)

        logger.info("Filtered repository files. repo_root=%s kept=%d", repo_root, len(kept))
        return kept


class MetadataExtractorService:
    def extract_and_store(self, repository: Repository, repo_root: Path, files: list[Path]) -> int:
        rows: list[FileMetadata] = []

        for f in files:
            try:
                st = f.stat()
            except OSError:
                continue

            created = datetime.fromtimestamp(getattr(st, "st_ctime", st.st_mtime), tz=timezone.utc)
            modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)

            rel = safe_relpath(f, repo_root)
            rows.append(
                FileMetadata(
                    repository=repository,
                    file_path=rel,
                    file_name=f.name,
                    extension=f.suffix.lower().lstrip("."),
                    size_bytes=st.st_size,
                    created_at=created,
                    modified_at=modified,
                )
            )

        with transaction.atomic():
            FileMetadata.objects.filter(repository=repository).delete()
            FileMetadata.objects.bulk_create(rows, batch_size=1000)
            repository.status = Repository.Status.INGESTED
            repository.last_error = ""
            repository.save(update_fields=["status", "last_error", "updated_at"])

        logger.info("Stored file metadata. repository=%s rows=%d", repository.id, len(rows))
        return len(rows)


class RepoIngestionService:
    def __init__(
        self,
        cloner: RepoClonerService | None = None,
        filterer: FileFilterService | None = None,
        extractor: MetadataExtractorService | None = None,
    ) -> None:
        self.cloner = cloner or RepoClonerService()
        self.filterer = filterer or FileFilterService()
        self.extractor = extractor or MetadataExtractorService()

    def run(self, repository: Repository) -> dict:
        logger.info("Starting ingestion. repository=%s", repository.id)
        repository.status = Repository.Status.CLONING
        repository.last_error = ""
        repository.save(update_fields=["status", "last_error", "updated_at"])

        try:
            repo_root = self.cloner.clone(repository)
            files = self.filterer.iter_relevant_files(repo_root)
            if not files:
                raise IngestionError("Repository contained no relevant files after filtering.")
            stored = self.extractor.extract_and_store(repository, repo_root, files)

            repository.refresh_from_db()
            file_rows = list(FileMetadata.objects.filter(repository=repository).order_by("file_path"))

            tree = build_tree([f.file_path for f in file_rows])
            tree_text = render_tree_box_drawing(tree)

            detected = TechStackDetectorService().detect(
                repository=repository, repo_root=repo_root, repo_tree_text=tree_text
            )
            repository.tech_stack = detected
            repository.save(update_fields=["tech_stack", "updated_at"])

            selector = StackAwareFileSelectorService()
            selection = selector.select(repository=repository, files=file_rows)

            with transaction.atomic():
                FileMetadata.objects.filter(repository=repository).update(
                    is_selected=False, selection_reason=""
                )
                for f in file_rows:
                    if f.file_path in selection.selected_paths:
                        f.is_selected = True
                        f.selection_reason = selection.reasons_by_path.get(f.file_path, "")
                FileMetadata.objects.bulk_update(
                    file_rows, ["is_selected", "selection_reason"], batch_size=1000
                )
        except Exception as e:
            logger.exception("Ingestion failed. repository=%s", repository.id)
            repository.status = Repository.Status.FAILED
            repository.last_error = str(e)
            repository.save(update_fields=["status", "last_error", "updated_at"])
            raise

        selected_count = FileMetadata.objects.filter(repository=repository, is_selected=True).count()
        return {
            "repository_id": str(repository.id),
            "file_count": stored,
            "selected_file_count": selected_count,
            "local_path": str(repo_root),
            "tech_stack": repository.tech_stack,
        }

