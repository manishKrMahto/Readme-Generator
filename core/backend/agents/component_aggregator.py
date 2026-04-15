from __future__ import annotations

from dataclasses import dataclass

from core.backend.agents.types import JsonDict


@dataclass(frozen=True)
class AggregatedComponents:
    title: str
    table_of_contents: str
    tech_stack: JsonDict
    description: str
    architecture_diagram: str
    api_endpoints: list[dict]
    file_structure: str
    installation: str
    future_improvements: str

    def to_dict(self) -> JsonDict:
        return {
            "title": self.title,
            "table_of_contents": self.table_of_contents,
            "tech_stack": self.tech_stack,
            "description": self.description,
            "architecture_diagram": self.architecture_diagram,
            "api_endpoints": self.api_endpoints,
            "file_structure": self.file_structure,
            "installation": self.installation,
            "future_improvements": self.future_improvements,
        }


class ComponentAggregator:
    def aggregate(self, outputs: JsonDict) -> AggregatedComponents:
        desc = outputs.get("project_description") or {}
        tech = outputs.get("tech_stack_detection") or {}
        api = outputs.get("api_endpoints") or []
        return AggregatedComponents(
            title=str(outputs.get("project_title") or "").strip(),
            table_of_contents=str(outputs.get("table_of_contents") or "").strip(),
            tech_stack=tech if isinstance(tech, dict) else {},
            description=str(desc.get("description") or "").strip(),
            architecture_diagram=str(desc.get("architecture_diagram") or "").strip(),
            api_endpoints=list(api or []),
            file_structure=str(outputs.get("file_structure") or "").strip(),
            installation=str(outputs.get("installation_instructions") or "").strip(),
            future_improvements=str(outputs.get("future_improvements") or "").strip(),
        )

