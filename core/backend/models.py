from __future__ import annotations

import uuid

from django.db import models


class Repository(models.Model):
    class TechStack(models.TextChoices):
        DJANGO = "django", "Django"
        FASTAPI = "fastapi", "FastAPI"
        REACT_FRONTEND = "react_frontend", "React (frontend)"
        NODE_BACKEND = "node_backend", "Node.js (backend)"
        REACT_NATIVE = "react_native", "React Native"
        JAVA_APP = "java_app", "Java app"
        UNKNOWN = "unknown", "Unknown"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLONING = "cloning", "Cloning"
        INGESTED = "ingested", "Ingested"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repo_url = models.URLField(unique=True)

    local_path = models.TextField(blank=True)
    tech_stack = models.CharField(
        max_length=64, choices=TechStack.choices, default=TechStack.UNKNOWN
    )

    # Latest generated README sections (persisted after compose).
    readme_title = models.CharField(max_length=512, blank=True)
    readme_tagline = models.CharField(max_length=512, blank=True)
    readme_table_of_contents = models.TextField(blank=True)
    readme_description = models.TextField(blank=True)
    readme_code_structure = models.TextField(blank=True)
    readme_future_improvements = models.TextField(blank=True)
    readme_full = models.TextField(blank=True)
    readme_generated_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.repo_url} ({self.status})"


class FileMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="files"
    )

    file_path = models.TextField(help_text="Path relative to the cloned repo root.")
    file_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=32, blank=True)
    size_bytes = models.BigIntegerField()

    is_selected = models.BooleanField(default=True)
    selection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(null=True, blank=True)
    indexed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "file_path"], name="uniq_repo_file_path"
            )
        ]
        indexes = [
            models.Index(fields=["repository", "extension"]),
            models.Index(fields=["repository", "size_bytes"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.file_path


class CodeChunk(models.Model):
    class ChunkType(models.TextChoices):
        FILE = "file", "File"
        CLASS = "class", "Class"
        FUNCTION = "function", "Function"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="chunks"
    )
    file = models.ForeignKey(
        FileMetadata, on_delete=models.CASCADE, related_name="chunks"
    )

    chunk_type = models.CharField(
        max_length=16, choices=ChunkType.choices, default=ChunkType.OTHER
    )
    symbol_name = models.CharField(max_length=255, blank=True)
    start_line = models.IntegerField(null=True, blank=True)
    end_line = models.IntegerField(null=True, blank=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["repository", "chunk_type"]),
            models.Index(fields=["repository", "file"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.repository_id}:{self.file_id}:{self.chunk_type}:{self.symbol_name}"


class AgentOutput(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="agent_outputs"
    )

    agent_name = models.CharField(max_length=128)
    agent_version = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SUCCESS
    )
    output = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["repository", "agent_name"]),
            models.Index(fields=["repository", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.agent_name} ({self.repository_id})"


class ReadmeGenerationMonitor(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="readme_generation_monitors"
    )
    repo_url = models.URLField()

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STARTED)
    model = models.CharField(max_length=128, blank=True)

    # Pipeline timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_execution_time_ms = models.IntegerField(default=0)

    # JSON-first observability payloads
    agent_logs = models.JSONField(default=dict, blank=True)
    llm_calls = models.JSONField(default=list, blank=True)
    llm_call_count = models.IntegerField(default=0)

    # Token + cost summary
    total_input_tokens = models.IntegerField(default=0)
    total_output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    total_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    # Generated outputs
    readme_content = models.TextField(blank=True)
    readme_sections = models.JSONField(default=dict, blank=True)

    # Error handling
    error_message = models.TextField(blank=True)
    failed_step = models.CharField(max_length=128, blank=True)

    # Debug metadata
    detected_tech_stack = models.JSONField(default=dict, blank=True)
    total_files_processed = models.IntegerField(default=0)
    total_chunks_created = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["repo_url", "created_at"]),
            models.Index(fields=["repository", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"README monitor {self.repository_id} ({self.status})"

