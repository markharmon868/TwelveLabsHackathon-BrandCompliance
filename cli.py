#!/usr/bin/env python3
"""
Brand Integration Auditor — CLI

Usage:
    python cli.py <video_path> <guidelines_json> [options]

Examples:
    # Full run — creates index, uploads video, runs audit
    python cli.py videos/ad_spot.mp4 guidelines/pureflow_water.json

    # Re-audit using an already-indexed video (skips upload)
    python cli.py videos/ad_spot.mp4 guidelines/pureflow_water.json \\
        --index-id <index_id> --video-id <video_id>
"""

import argparse
import json
import sys
from pathlib import Path

from brand_compliance import (
    create_index,
    upload_video,
    analyze_brand_compliance,
    Guidelines,
    ComplianceReport,
    print_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Brand integration audit powered by TwelveLabs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video_path", help="Path to the video file to audit")
    parser.add_argument("guidelines_json", help="Path to the brand guidelines JSON file")

    reuse = parser.add_argument_group("re-use an existing index (skips upload)")
    reuse.add_argument("--index-id", metavar="INDEX_ID",
                       help="Use an existing TwelveLabs index")
    reuse.add_argument("--video-id", metavar="VIDEO_ID",
                       help="Use an already-indexed video ID (requires --index-id)")

    return parser.parse_args()


def load_guidelines(path: str) -> Guidelines:
    p = Path(path)
    if not p.exists():
        print(f"Error: Guidelines file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with p.open() as f:
            data = json.load(f)
        return Guidelines.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error: Invalid guidelines JSON — {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    guidelines = load_guidelines(args.guidelines_json)

    print(f"\nBrand Integration Auditor")
    print(f"Brand         : {guidelines.brand}")
    print(f"Video         : {args.video_path}")
    print(f"Prohibited    : {len(guidelines.prohibited_contexts)} context(s)")
    print(f"Required      : {len(guidelines.required_contexts)} context(s)")
    print(f"Contracted    : {guidelines.contracted_screen_time_seconds}s screen time")
    print()

    # --- Index setup ---
    if args.index_id and args.video_id:
        index_id = args.index_id
        video_id = args.video_id
        print(f"Using existing index {index_id} / video {video_id}")
    elif args.index_id:
        index_id = args.index_id
        video_id = upload_video(index_id, args.video_path)
    else:
        index_name = guidelines.brand.lower().replace(" ", "_") + "_compliance"
        print(f"Creating index: {index_name}")
        index_id = create_index(index_name)
        print(f"Index: {index_id}")
        video_id = upload_video(index_id, args.video_path)

    # --- Analysis ---
    print(f"\nRunning audit...")
    appearances, violations = analyze_brand_compliance(
        index_id=index_id,
        video_id=video_id,
        guidelines=guidelines,
    )

    # --- Report ---
    report = ComplianceReport(
        brand=guidelines.brand,
        video_path=args.video_path,
        index_id=index_id,
        video_id=video_id,
        contracted_screen_time_seconds=guidelines.contracted_screen_time_seconds,
        appearances=appearances,
        violations=violations,
    )
    print_report(report)

    # CI-friendly exit codes
    if report.critical_count > 0:
        sys.exit(2)
    elif not report.is_compliant:
        sys.exit(1)


if __name__ == "__main__":
    main()
