from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from core.backend.models import Repository


@dataclass(frozen=True)
class TechStackDetectionInput:
    repo_tree_text: str
    key_files: dict[str, str]


class TechStackDetectorService:
    ALLOWED = {
        Repository.TechStack.DJANGO,
        Repository.TechStack.FASTAPI,
        Repository.TechStack.REACT_FRONTEND,
        Repository.TechStack.NODE_BACKEND,
        Repository.TechStack.REACT_NATIVE,
        Repository.TechStack.JAVA_APP,
        Repository.TechStack.UNKNOWN,
    }

    def _read_text(self, path: Path, max_chars: int) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except OSError:
            return ""

    def build_input(self, repo_root: Path, repo_tree_text: str) -> TechStackDetectionInput:
        key_paths = [
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "manage.py",
            "Dockerfile",
            "docker-compose.yml",
            "pom.xml",
            "build.gradle",
            "settings.py",
        ]
        key_files: dict[str, str] = {}
        for rel in key_paths:
            p = repo_root / rel
            if p.exists() and p.is_file():
                key_files[rel] = self._read_text(p, max_chars=12_000)
        return TechStackDetectionInput(repo_tree_text=repo_tree_text, key_files=key_files)

    def detect(self, repository: Repository, repo_root: Path, repo_tree_text: str) -> str:
        api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        model = getattr(settings, "OPENAI_MODEL", "") or ""
        if not api_key or not model:
            return Repository.TechStack.UNKNOWN

        payload = self.build_input(repo_root=repo_root, repo_tree_text=repo_tree_text)

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        system = (
            "You are a classifier that identifies a repository's primary tech stack. "
            "Return ONLY a JSON object with key 'tech_stack' whose value is one of: "
            f"{', '.join(sorted(self.ALLOWED))}."
        )
        user = {
            "repo_url": repository.repo_url,
            "repo_tree": payload.repo_tree_text[:25_000],
            "key_files": payload.key_files,
        }

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            temperature=0,
        )

        content = (resp.choices[0].message.content or "").strip()
        try:
            data = json.loads(content)
        except Exception:
            return Repository.TechStack.UNKNOWN

        label = (data.get("tech_stack") or "").strip()
        return label if label in self.ALLOWED else Repository.TechStack.UNKNOWN

