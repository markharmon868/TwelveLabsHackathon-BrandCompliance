from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Violation:
    timestamp_start: float
    timestamp_end: float
    brand: str
    prohibited_context: str
    explanation: str
    confidence: float  # 0.0 – 1.0
    severity: Literal["minor", "moderate", "critical"]


@dataclass
class BrandRule:
    context: str           # e.g. "violent scenes"
    description: str       # human-readable rule description
    severity: Literal["minor", "moderate", "critical"] = "moderate"


@dataclass
class Guidelines:
    brand_name: str
    rules: list[BrandRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Guidelines":
        rules = [
            BrandRule(
                context=r["context"],
                description=r["description"],
                severity=r.get("severity", "moderate"),
            )
            for r in data.get("rules", [])
        ]
        return cls(brand_name=data["brand_name"], rules=rules)


@dataclass
class ComplianceReport:
    brand: str
    video_path: str
    index_id: str
    video_id: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return len(self.violations) == 0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "critical")

    @property
    def moderate_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "moderate")

    @property
    def minor_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "minor")
