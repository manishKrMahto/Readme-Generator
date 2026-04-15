from __future__ import annotations

from django.contrib import admin

from core.backend.models import ReadmeGenerationMonitor


@admin.register(ReadmeGenerationMonitor)
class ReadmeGenerationMonitorAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "repo_url",
        "status",
        "total_execution_time_ms",
    )
    list_filter = ("status", "created_at")
    search_fields = ("repo_url", "repository__repo_url")
    readonly_fields = (
        "id",
        "repository",
        "repo_url",
        "status",
        "model",
        "started_at",
        "completed_at",
        "total_execution_time_ms",
        "agent_logs",
        "readme_sections",
        "readme_content",
        "error_message",
        "failed_step",
        "detected_tech_stack",
        "total_files_processed",
        "total_chunks_created",
        "created_at",
        "updated_at",
    )
    # Hide LLM observability fields from Django Admin completely.
    exclude = (
        "llm_calls",
        "llm_call_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_tokens",
        "total_cost_usd",
    )
    ordering = ("-created_at",)

