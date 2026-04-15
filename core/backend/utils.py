from __future__ import annotations

import os
from pathlib import Path


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "venv",
    ".venv",
    "env",
    "build",
    "dist",
    "target",
    ".next",
    ".turbo",
}


DEFAULT_ALLOWED_EXTENSIONS = {
    # Common source code
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    # Config/docs
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".dockerfile",
    ".sh",
    ".bat",
    ".ps1",
    # Build tooling
    ".gradle",
    ".properties",
    ".xml",
}


def is_binary_file(path: Path, sniff_bytes: int = 2048) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(sniff_bytes)
        return b"\x00" in chunk
    except OSError:
        return True


def safe_relpath(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return rel.as_posix()


def should_exclude_dir(dirname: str, excluded_dirs: set[str]) -> bool:
    base = os.path.basename(dirname)
    return base in excluded_dirs

