from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.backend.models import CodeChunk, FileMetadata, Repository
from core.backend.models import ReadmeGenerationMonitor


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class AgentContext:
    repository: Repository
    monitor: ReadmeGenerationMonitor
    repo_root: Path
    files: list[FileMetadata]
    chunks: list[CodeChunk]
    folder_paths: list[str]
    tree_text: str
    existing_readme_text: str | None


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return int(self.input_tokens) + int(self.output_tokens)

