"""
Core brand compliance analysis using TwelveLabs.

Strategy (two-pass):
  Pass 1 — Marengo search: find all clips where the brand appears, using
           the logo description and brand name as search queries.

  Pass 2 — Pegasus classify: for each brand appearance, ask Pegasus to
           determine whether it's compliant, a violation, or needs human
           review. Pegasus checks all prohibited and required contexts in
           a single call per clip.
"""

import json
import re
from typing import Any

from .client import get_client
from .models import Appearance, Guidelines, Violation

# Use "none" to return all clips regardless of score — Pegasus filters in pass 2.
_SEARCH_THRESHOLD = "none"

# Cap on brand appearance clips to evaluate (avoids runaway API costs).
_MAX_BRAND_CLIPS = 10

# Pegasus confidence below this → "needs_review" instead of auto-classifying.
_REVIEW_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_brand_compliance(
    index_id: str,
    video_id: str,
    guidelines: Guidelines,
    api_key: str | None = None,
) -> tuple[list[Appearance], list[Violation]]:
    """
    Scan a video for brand appearances and compliance violations.

    Returns
    -------
    appearances : every clip where the brand was detected (compliant / violation / needs_review)
    violations  : subset of appearances that breach a prohibited context rule
    """
    client = get_client(api_key)

    # --- Pass 1: find all brand appearance clips via Marengo ---
    print(f"  Searching for '{guidelines.brand}' appearances...")
    raw_clips = _find_brand_appearances(client, index_id, video_id, guidelines)
    if not raw_clips:
        print("  No brand appearances found in video.")
        return [], []

    print(f"  Found {len(raw_clips)} candidate clip(s). Classifying with Pegasus...")

    # --- Pass 2: classify each clip with Pegasus ---
    appearances: list[Appearance] = []
    violations: list[Violation] = []

    for clip in raw_clips:
        appearance = _classify_appearance(client, video_id, guidelines, clip)
        appearances.append(appearance)
        if appearance.violation:
            violations.append(appearance.violation)

    # Sort by timestamp and deduplicate overlapping violations
    appearances.sort(key=lambda a: a.timestamp_start)
    violations = _deduplicate(violations)

    return appearances, violations


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_brand_appearances(
    client: Any,
    index_id: str,
    video_id: str,
    guidelines: Guidelines,
) -> list[dict]:
    """
    Use Marengo to find clips where the brand appears.
    Searches using both the brand name and logo description for best recall.
    Returns a list of dicts: {start, end, score}.
    """
    queries = [guidelines.brand]
    if guidelines.logo_description:
        queries.append(guidelines.logo_description)

    seen: dict[tuple, dict] = {}  # (start, end) → clip, to deduplicate across queries

    for query in queries:
        try:
            results = client.search.create(
                index_id=index_id,
                query_text=query,
                search_options=["visual"],
                threshold=_SEARCH_THRESHOLD,
                group_by="clip",
                page_limit=_MAX_BRAND_CLIPS,
            )
        except Exception as e:
            print(f"    Search error for '{query}': {e}")
            continue

        for item in (results.data or []):
            if item.video_id != video_id:
                continue
            key = (round(item.start, 1), round(item.end, 1))
            if key not in seen or item.score > seen[key]["score"]:
                seen[key] = {"start": item.start, "end": item.end, "score": item.score}

    clips = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
    return clips[:_MAX_BRAND_CLIPS]


def _classify_appearance(
    client: Any,
    video_id: str,
    guidelines: Guidelines,
    clip: dict,
) -> Appearance:
    """
    Ask Pegasus to classify a single brand appearance clip.
    Returns an Appearance (with an embedded Violation if one was detected).
    """
    clip_start = clip["start"]
    clip_end = clip["end"]
    search_score = clip["score"]

    prompt = _build_classification_prompt(guidelines, clip_start, clip_end)

    try:
        response = client.analyze(video_id=video_id, prompt=prompt)
        raw_text = response.data or ""
    except Exception as e:
        print(f"    Pegasus error at {clip_start:.1f}s–{clip_end:.1f}s: {e}")
        return _needs_review_appearance(guidelines.brand, clip_start, clip_end, str(e))

    parsed = _parse_pegasus_response(raw_text)
    if not parsed:
        return _needs_review_appearance(
            guidelines.brand, clip_start, clip_end,
            "Could not parse Pegasus response — flagged for human review."
        )

    # Blend Marengo search score with Pegasus confidence
    marengo_conf = search_score / 100.0 if search_score > 1.0 else search_score
    pegasus_conf = float(parsed.get("confidence", 0.7))
    confidence = round(0.4 * marengo_conf + 0.6 * pegasus_conf, 3)

    brand_detected = parsed.get("brand_detected", False)
    if not brand_detected:
        # Marengo found it but Pegasus disagrees — treat as needs_review if borderline
        if confidence >= _REVIEW_THRESHOLD:
            return _needs_review_appearance(
                guidelines.brand, clip_start, clip_end,
                parsed.get("explanation", "Brand detection uncertain.")
            )
        # Low confidence and Pegasus says no brand — skip
        return Appearance(
            timestamp_start=clip_start,
            timestamp_end=clip_end,
            brand=guidelines.brand,
            confidence=confidence,
            status="needs_review",
            explanation=parsed.get("explanation", "Brand not confirmed in this segment."),
        )

    if confidence < _REVIEW_THRESHOLD:
        return _needs_review_appearance(
            guidelines.brand, clip_start, clip_end,
            parsed.get("explanation", "Low confidence detection — flagged for human review.")
        )

    # Check for a violation
    violated_context = parsed.get("violated_context")
    if violated_context:
        severity = guidelines.severity_for(violated_context)
        explanation = parsed.get("explanation", "")
        violation = Violation(
            timestamp_start=clip_start,
            timestamp_end=clip_end,
            brand=guidelines.brand,
            prohibited_context=violated_context,
            explanation=explanation,
            confidence=confidence,
            severity=severity,
        )
        return Appearance(
            timestamp_start=clip_start,
            timestamp_end=clip_end,
            brand=guidelines.brand,
            confidence=confidence,
            status="violation",
            explanation=explanation,
            violation=violation,
        )

    return Appearance(
        timestamp_start=clip_start,
        timestamp_end=clip_end,
        brand=guidelines.brand,
        confidence=confidence,
        status="compliant",
        explanation=parsed.get("explanation", "Brand appears in a compliant context."),
    )


def _needs_review_appearance(
    brand: str, start: float, end: float, explanation: str
) -> Appearance:
    return Appearance(
        timestamp_start=start,
        timestamp_end=end,
        brand=brand,
        confidence=0.0,
        status="needs_review",
        explanation=explanation,
    )


def _build_classification_prompt(
    guidelines: Guidelines, clip_start: float, clip_end: float
) -> str:
    prohibited = "\n".join(f'  - "{c}"' for c in guidelines.prohibited_contexts)
    required = "\n".join(f'  - "{c}"' for c in guidelines.required_contexts)

    return f"""You are a brand integration auditor reviewing a video segment from approximately {clip_start:.1f}s to {clip_end:.1f}s.

Brand being monitored: "{guidelines.brand}"
Logo / visual identity: "{guidelines.logo_description}"

PROHIBITED contexts (brand must NOT appear in these):
{prohibited or "  (none specified)"}

REQUIRED contexts (brand SHOULD appear in these to fulfill the contract):
{required or "  (none specified)"}

Carefully analyze this video segment and respond ONLY with a valid JSON object — no markdown, no code fences, no extra text.

{{
  "brand_detected": true or false,
  "confidence": 0.0 to 1.0,
  "violated_context": "exact prohibited context string from the list above, or null if none violated",
  "explanation": "Two to four sentences. State whether the brand is visible, describe exactly what is happening in the scene, and explain why it is or is not a violation. Be specific — name objects, actions, and setting. A brand manager must understand this without watching the clip."
}}

Rules for your response:
- "brand_detected" is true only if "{guidelines.brand}" logo, name, product, or packaging is clearly visible or audibly mentioned.
- "violated_context" must be copied exactly from the prohibited contexts list above, or null.
- Only report one violated_context — the most severe one if multiple apply.
- "confidence" is your certainty that brand_detected and violated_context are correct (1.0 = certain).
- If the brand is partially obscured or ambiguous, set confidence below 0.6.
- The explanation must be specific enough for a non-technical brand manager to understand without watching the clip."""


def _parse_pegasus_response(raw_text: str) -> dict | None:
    """Extract and parse the JSON object from Pegasus's response text."""
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    """
    Remove duplicate violations where the same prohibited context fires on
    heavily overlapping clips. Keeps the higher-confidence entry.
    """
    if len(violations) <= 1:
        return violations

    violations = sorted(violations, key=lambda v: v.confidence, reverse=True)
    kept: list[Violation] = []

    for candidate in violations:
        overlaps = False
        for existing in kept:
            if existing.prohibited_context != candidate.prohibited_context:
                continue
            overlap_start = max(candidate.timestamp_start, existing.timestamp_start)
            overlap_end = min(candidate.timestamp_end, existing.timestamp_end)
            overlap_duration = max(0.0, overlap_end - overlap_start)
            candidate_duration = candidate.timestamp_end - candidate.timestamp_start
            if candidate_duration > 0 and overlap_duration / candidate_duration > 0.5:
                overlaps = True
                break
        if not overlaps:
            kept.append(candidate)

    return sorted(kept, key=lambda v: v.timestamp_start)
