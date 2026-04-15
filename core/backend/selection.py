from __future__ import annotations

from dataclasses import dataclass

from core.backend.models import FileMetadata, Repository


@dataclass(frozen=True)
class SelectionResult:
    selected_paths: set[str]
    reasons_by_path: dict[str, str]


class StackAwareFileSelectorService:
    ALWAYS_KEEP_NAMES = {
        "readme",
        "readme.md",
        "readme.rst",
        "license",
        "license.md",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".gitignore",
        ".dockerignore",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "tsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "webpack.config.js",
        "pom.xml",
        "build.gradle",
        "gradle.properties",
        "settings.gradle",
        "compose.yaml",
        "compose.yml",
    }

    ALWAYS_KEEP_PREFIXES = (
        ".github/workflows/",
        ".gitlab-ci",
    )

    def _is_entrypoint(self, p: str) -> bool:
        name = p.rsplit("/", 1)[-1].lower()
        return name in {"manage.py", "main.py", "app.py", "server.py", "index.js", "index.ts"}

    def _keep_reason_base(self, f: FileMetadata) -> str | None:
        name = (f.file_name or "").lower()
        path = (f.file_path or "").lower()
        if name in self.ALWAYS_KEEP_NAMES:
            return "key project/config file"
        if any(path.startswith(pref) for pref in self.ALWAYS_KEEP_PREFIXES):
            return "ci/cd configuration"
        if self._is_entrypoint(path):
            return "common entrypoint"
        return None

    def _keep_reason_stack(self, tech_stack: str, f: FileMetadata) -> str | None:
        path = (f.file_path or "").lower()
        name = (f.file_name or "").lower()

        if tech_stack == Repository.TechStack.DJANGO:
            if name in {"settings.py", "urls.py", "wsgi.py", "asgi.py"}:
                return "django core configuration"
            if name in {"models.py", "views.py", "serializers.py", "admin.py", "apps.py"}:
                return "django app structure"
            if "/migrations/" in path:
                return "database schema migrations"
            if path.startswith("templates/") or "/templates/" in path:
                return "django templates"

        if tech_stack == Repository.TechStack.FASTAPI:
            if name in {"main.py", "app.py"}:
                return "fastapi entrypoint"
            if "/routers/" in path or "/routes/" in path:
                return "api routing"
            if "/schemas/" in path or "/models/" in path:
                return "api/data models"

        if tech_stack == Repository.TechStack.REACT_FRONTEND:
            if name in {"package.json", "tsconfig.json"}:
                return "frontend configuration"
            if path.startswith("src/") or "/src/" in path:
                return "frontend source"
            if name.startswith("vite.config") or name.startswith("webpack.config"):
                return "frontend tooling config"

        if tech_stack == Repository.TechStack.NODE_BACKEND:
            if name == "package.json":
                return "backend configuration"
            if path.startswith("src/") or "/src/" in path:
                return "backend source"
            if "/routes/" in path or "/controllers/" in path or "/services/" in path:
                return "backend architecture"

        if tech_stack == Repository.TechStack.REACT_NATIVE:
            if name == "app.json" or name == "metro.config.js":
                return "react native configuration"
            if path.startswith("src/") or "/src/" in path:
                return "react native source"
            if "/android/" in path or "/ios/" in path:
                return "mobile platform project"

        if tech_stack == Repository.TechStack.JAVA_APP:
            if path.startswith("src/main/java/") or "/src/main/java/" in path:
                return "java application source"
            if name in {"pom.xml", "build.gradle"}:
                return "java build configuration"

        return None

    def select(self, repository: Repository, files: list[FileMetadata]) -> SelectionResult:
        tech_stack = repository.tech_stack or Repository.TechStack.UNKNOWN
        selected: set[str] = set()
        reasons: dict[str, str] = {}

        for f in files:
            base_reason = self._keep_reason_base(f)
            if base_reason:
                selected.add(f.file_path)
                reasons[f.file_path] = base_reason
                continue

            stack_reason = self._keep_reason_stack(tech_stack, f)
            if stack_reason:
                selected.add(f.file_path)
                reasons[f.file_path] = stack_reason

        if not selected:
            selected = {f.file_path for f in files}
            reasons = {f.file_path: "fallback: keep all filtered files" for f in files}

        return SelectionResult(selected_paths=selected, reasons_by_path=reasons)

