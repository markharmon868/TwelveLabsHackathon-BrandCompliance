from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Guidelines — loaded from a user-supplied JSON file
# ---------------------------------------------------------------------------

@dataclass
class Guidelines:
    brand: str
    logo_description: str                          # text description of the logo for search
    contracted_screen_time_seconds: float          # minimum delivery requirement
    required_contexts: list[str]                   # contexts the brand SHOULD appear in
    prohibited_contexts: list[str]                 # contexts the brand must NOT appear in
    severity_overrides: dict[str, Literal["minor", "moderate", "critical"]]  # per-context severity
    search_queries: list[str] = field(default_factory=list)  # optional explicit Marengo search queries

    @classmethod
    def from_dict(cls, data: dict) -> "Guidelines":
        return cls(
            brand=data["brand"],
            logo_description=data.get("logo_description", ""),
            contracted_screen_time_seconds=float(data.get("contracted_screen_time_seconds", 0)),
            required_contexts=data.get("required_contexts", []),
            prohibited_contexts=data.get("prohibited_contexts", []),
            severity_overrides=data.get("severity_overrides", {}),
            search_queries=data.get("search_queries", []),
        )

    def severity_for(self, context: str) -> Literal["minor", "moderate", "critical"]:
        return self.severity_overrides.get(context, "moderate")


# ---------------------------------------------------------------------------
# Violation — a single prohibited context breach
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    timestamp_start: float
    timestamp_end: float
    brand: str
    prohibited_context: str
    explanation: str
    confidence: float                              # 0.0 – 1.0
    severity: Literal["minor", "moderate", "critical"]


# ---------------------------------------------------------------------------
# Appearance — a single detected brand appearance in the video
# ---------------------------------------------------------------------------

@dataclass
class Appearance:
    timestamp_start: float
    timestamp_end: float
    brand: str
    confidence: float
    status: Literal["compliant", "violation", "needs_review"]
    explanation: str
    violation: Violation | None = None             # set when status == "violation"

    @property
    def duration(self) -> float:
        return max(0.0, self.timestamp_end - self.timestamp_start)


# ---------------------------------------------------------------------------
# ComplianceReport — full audit result for one video + one brand
# ---------------------------------------------------------------------------

@dataclass
class ComplianceReport:
    brand: str
    video_path: str
    index_id: str
    video_id: str
    contracted_screen_time_seconds: float
    appearances: list[Appearance] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    # --- Screen time ---

    @property
    def delivered_screen_time_seconds(self) -> float:
        """Total seconds the brand appears with confirmed detections."""
        return sum(
            a.duration for a in self.appearances
            if a.status in ("compliant", "violation")
        )

    @property
    def screen_time_gap_seconds(self) -> float:
        return max(0.0, self.contracted_screen_time_seconds - self.delivered_screen_time_seconds)

    @property
    def is_under_delivered(self) -> bool:
        return (
            self.contracted_screen_time_seconds > 0
            and self.delivered_screen_time_seconds < self.contracted_screen_time_seconds
        )

    # --- Appearance counts ---

    @property
    def compliant_count(self) -> int:
        return sum(1 for a in self.appearances if a.status == "compliant")

    @property
    def needs_review_count(self) -> int:
        return sum(1 for a in self.appearances if a.status == "needs_review")

    # --- Violation counts ---

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "critical")

    @property
    def moderate_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "moderate")

    @property
    def minor_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "minor")

    # --- Overall status ---

    @property
    def delivery_status(self) -> Literal["COMPLIANT", "VIOLATION", "UNDER-DELIVERED"]:
        if self.violations:
            return "VIOLATION"
        if self.is_under_delivered:
            return "UNDER-DELIVERED"
        return "COMPLIANT"

    @property
    def is_compliant(self) -> bool:
        return self.delivery_status == "COMPLIANT"
