from __future__ import annotations

from core.backend.models import Repository


def folder_comment_for_path(path: str, tech_stack: str) -> str:
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "Repository root."

    last = parts[-1].lower()
    by_name: dict[str, str] = {
        "__pycache__": "Python bytecode cache (auto-generated).",
        "migrations": "Database migration scripts for schema changes.",
        "static": "Static assets (CSS, JavaScript, images) for the web UI.",
        "staticfiles": "Collected static files for production (Django `collectstatic`).",
        "templates": "Server-rendered HTML templates.",
        "media": "User-uploaded or runtime media files.",
        "locale": "Translation / locale files for internationalization.",
        "components": "Reusable UI components.",
        "hooks": "Custom hooks (e.g. React hooks).",
        "context": "Shared context providers (e.g. React context).",
        "pages": "Route-level pages or top-level views.",
        "views": "View layer (HTTP handlers or MVC views).",
        "serializers": "API serializers / request-response shaping.",
        "models": "Data models (ORM entities or domain models).",
        "admin": "Admin registration and back-office configuration.",
        "tests": "Automated tests.",
        "test": "Test helpers or legacy test layout.",
        "__tests__": "Frontend or Jest-style tests.",
        ".github": "GitHub Actions workflows and GitHub metadata.",
        "public": "Public assets for the web app shell (e.g. `index.html`).",
        "dist": "Compiled or bundled output (often not edited by hand).",
        "build": "Build output or intermediate artifacts.",
        "node_modules": "Installed JavaScript dependencies (usually gitignored).",
        "venv": "Python virtual environment (usually not committed).",
        ".venv": "Python virtual environment (usually not committed).",
        "api": "HTTP API surface (handlers, routers, or controllers).",
        "routes": "Route definitions.",
        "controllers": "Request controllers / handlers.",
        "services": "Business logic or integrations with external systems.",
        "schemas": "Validation schemas, DTOs, or OpenAPI models.",
        "routers": "Sub-routers (e.g. FastAPI `APIRouter`).",
        "middleware": "HTTP middleware.",
        "utils": "Shared helpers and small utilities.",
        "lib": "Shared library code.",
        "config": "Application configuration.",
        "settings": "Environment-specific or framework settings.",
        "job_pipeline": "Jobs, pipelines, or batch processing for this feature area.",
        "landing": "Landing or marketing pages for the product.",
        "courses": "Course-related features and workflows.",
        "accounts": "User accounts: auth, profiles, and account settings.",
        "core": "Project-wide core: settings, URLs, or shared infrastructure.",
    }

    if last in by_name:
        return by_name[last]

    if tech_stack == Repository.TechStack.DJANGO and len(parts) == 1:
        return f"Django application or feature package `{last}`."
    if tech_stack == Repository.TechStack.REACT_FRONTEND and len(parts) == 1:
        return f"Frontend module or feature area `{last}`."
    if tech_stack == Repository.TechStack.REACT_NATIVE and len(parts) == 1:
        return f"React Native module or screen group `{last}`."
    if tech_stack == Repository.TechStack.NODE_BACKEND and len(parts) == 1:
        return f"Backend module `{last}`."
    if tech_stack == Repository.TechStack.JAVA_APP and (
        "src/main/java" in path or path.startswith("src/main/java")
    ):
        return "Java source package (standard Maven/Gradle layout)."

    return f"Project directory `{path}`."

