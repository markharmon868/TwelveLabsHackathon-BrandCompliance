"""
Core brand compliance analysis using TwelveLabs.

Strategy (two-pass):
  Pass 1 — Marengo search: for each prohibited context, find clips in the video
           that visually or audibly match that context. This narrows the search
           space without burning Pegasus quota on clean segments.

  Pass 2 — Pegasus analyze: for each candidate clip, ask Pegasus whether the
           brand is actually visible/mentioned AND whether the prohibited context
           is genuinely present. Pegasus returns a structured JSON answer which
           we parse into Violation objects.
"""

import json
import re
from typing import Any

from .client import get_client
from .models import BrandRule, Violation

# Marengo search confidence threshold — clips below this are ignored in pass 1.
_SEARCH_THRESHOLD = "low"

# How many search results to evaluate per rule (cap to avoid excessive API calls).
_MAX_CLIPS_PER_RULE = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_brand_compliance(
    index_id: str,
    video_id: str,
    brand_name: str,
    rules: list[BrandRule],
) -> list[Violation]:
    """
    Scan a video for brand safety violations.

    Parameters
    ----------
    index_id   : TwelveLabs index that contains the video.
    video_id   : The video to analyse.
    brand_name : Brand whose appearance we're monitoring (e.g. "PureFlow Water").
    rules      : List of BrandRule objects defining prohibited contexts.

    Returns a list of Violation objects (may be empty if video is clean).
    """
    client = get_client()
    violations: list[Violation] = []

    for rule in rules:
        print(f"  Scanning for: '{rule.context}'...")

        # --- Pass 1: find candidate clips via Marengo search ---
        candidates = _search_clips(client, index_id, video_id, rule.context)
        if not candidates:
            print(f"    No candidate clips found.")
            continue

        print(f"    Found {len(candidates)} candidate clip(s). Verifying with Pegasus...")

        # --- Pass 2: verify each clip with Pegasus ---
        for clip in candidates:
            violation = _verify_clip(
                client=client,
                video_id=video_id,
                brand_name=brand_name,
                rule=rule,
                clip_start=clip["start"],
                clip_end=clip["end"],
                search_score=clip["score"],
            )
            if violation:
                violations.append(violation)

    # Deduplicate overlapping violations (same context, overlapping timestamps)
    return _deduplicate(violations)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _search_clips(
    client: Any,
    index_id: str,
    video_id: str,
    context_query: str,
) -> list[dict]:
    """
    Use Marengo to find clips that match the prohibited context query.
    Returns a list of dicts with keys: start, end, score.
    """
    try:
        results = client.search.create(
            index_id=index_id,
            query_text=context_query,
            search_options=["visual", "audio"],
            threshold=_SEARCH_THRESHOLD,
            group_by="clip",
            page_limit=_MAX_CLIPS_PER_RULE,
        )
    except Exception as e:
        print(f"    Search error for '{context_query}': {e}")
        return []

    clips = []
    for item in (results.data or []):
        # Filter to this specific video (index may contain multiple videos)
        if item.video_id != video_id:
            continue
        clips.append({
            "start": item.start,
            "end": item.end,
            "score": item.score,
        })

    return clips[:_MAX_CLIPS_PER_RULE]


def _verify_clip(
    client: Any,
    video_id: str,
    brand_name: str,
    rule: BrandRule,
    clip_start: float,
    clip_end: float,
    search_score: float,
) -> Violation | None:
    """
    Ask Pegasus to verify whether the brand is present alongside the
    prohibited context in this clip. Returns a Violation or None.
    """
    prompt = _build_verification_prompt(
        brand_name=brand_name,
        rule=rule,
        clip_start=clip_start,
        clip_end=clip_end,
    )

    try:
        response = client.analyze(video_id=video_id, prompt=prompt)
        raw_text = response.data or ""
    except Exception as e:
        print(f"    Pegasus error at {clip_start:.1f}s–{clip_end:.1f}s: {e}")
        return None

    parsed = _parse_pegasus_response(raw_text)
    if not parsed:
        return None

    if not parsed.get("brand_detected") or not parsed.get("violation_detected"):
        return None

    # Blend Marengo search score with Pegasus confidence (weighted average)
    marengo_conf = search_score / 100.0 if search_score > 1.0 else search_score
    pegasus_conf = float(parsed.get("confidence", 0.7))
    confidence = round(0.4 * marengo_conf + 0.6 * pegasus_conf, 3)

    return Violation(
        timestamp_start=clip_start,
        timestamp_end=clip_end,
        brand=brand_name,
        prohibited_context=rule.context,
        explanation=parsed.get("explanation", raw_text[:300]),
        confidence=confidence,
        severity=rule.severity,
    )


def _build_verification_prompt(
    brand_name: str,
    rule: BrandRule,
    clip_start: float,
    clip_end: float,
) -> str:
    return f"""You are a brand safety analyst reviewing a video segment from approximately {clip_start:.1f}s to {clip_end:.1f}s.

Brand being monitored: "{brand_name}"
Prohibited context rule: "{rule.context}"
Rule description: "{rule.description}"

Carefully analyze this video segment and answer the following questions. Respond ONLY with a valid JSON object — no markdown, no code fences, no extra text.

{{
  "brand_detected": true or false,
  "violation_detected": true or false,
  "confidence": 0.0 to 1.0,
  "explanation": "One to three sentences describing exactly what you see and why it does or does not constitute a violation."
}}

Guidelines:
- "brand_detected" is true only if the "{brand_name}" brand logo, name, product, or packaging is clearly visible or audibly mentioned in this segment.
- "violation_detected" is true only if BOTH (a) the brand is detected AND (b) the prohibited context "{rule.context}" is present in this segment.
- "confidence" reflects how certain you are of your assessment (1.0 = completely certain).
- Be conservative: if the brand is ambiguous, set brand_detected to false."""


def _parse_pegasus_response(raw_text: str) -> dict | None:
    """
    Extract and parse the JSON object from Pegasus's response text.
    Handles cases where the model adds extra prose around the JSON.
    """
    # Try direct parse first
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON block with regex
    match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    """
    Remove duplicate violations where the same context fires on heavily
    overlapping clips. Keeps the higher-confidence violation.
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
            # Check for >50% temporal overlap
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
