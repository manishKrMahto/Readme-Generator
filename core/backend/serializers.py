from __future__ import annotations

from rest_framework import serializers


class GenerateReadmeRequestSerializer(serializers.Serializer):
    repo_url = serializers.URLField()


class GenerateReadmeResponseSerializer(serializers.Serializer):
    repository_id = serializers.UUIDField()
    status = serializers.CharField()
    task_id = serializers.CharField(required=False, allow_blank=True)

    readme = serializers.CharField(required=False, allow_blank=True)
    readme_full = serializers.CharField(required=False, allow_blank=True)
    readme_title = serializers.CharField(required=False, allow_blank=True)
    readme_tagline = serializers.CharField(required=False, allow_blank=True)
    readme_table_of_contents = serializers.CharField(required=False, allow_blank=True)
    readme_description = serializers.CharField(required=False, allow_blank=True)
    readme_code_structure = serializers.CharField(required=False, allow_blank=True)
    readme_future_improvements = serializers.CharField(required=False, allow_blank=True)
    readme_generated_at = serializers.DateTimeField(required=False, allow_null=True)

    tech_stack = serializers.CharField(required=False, allow_blank=True)
    filtered_file_count = serializers.IntegerField(required=False)
    selected_file_count = serializers.IntegerField(required=False)
    chunk_count = serializers.IntegerField(required=False)
    download_url = serializers.CharField(required=False, allow_blank=True)

    tokens_used = serializers.IntegerField(required=False)
    cost_estimate_usd = serializers.CharField(required=False, allow_blank=True)
    monitor_id = serializers.CharField(required=False, allow_blank=True)


class FileMetadataSerializer(serializers.Serializer):
    file_path = serializers.CharField()
    file_name = serializers.CharField()
    extension = serializers.CharField(allow_blank=True)
    size_bytes = serializers.IntegerField()


class CodeStructureSerializer(serializers.Serializer):
    file_path = serializers.CharField()
    imports = serializers.ListField(child=serializers.CharField(), required=False)
    classes = serializers.ListField(child=serializers.CharField(), required=False)
    functions = serializers.ListField(child=serializers.CharField(), required=False)

