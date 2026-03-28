#!/usr/bin/env python3
"""
Brand Compliance CLI

Usage:
    python cli.py <video_path> <brand_name> <guidelines_json> [--index-id INDEX_ID]

Examples:
    # Analyse a new video (creates a fresh index automatically)
    python cli.py videos/ad_spot.mp4 "PureFlow Water" guidelines/pureflow_water.json

    # Re-analyse using an existing index (skips upload/indexing)
    python cli.py videos/ad_spot.mp4 "PureFlow Water" guidelines/pureflow_water.json \\
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
        description="Brand compliance video analysis powered by TwelveLabs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("video_path", help="Path to the video file to analyse")
    parser.add_argument("brand_name", help="Brand name to monitor (e.g. 'PureFlow Water')")
    parser.add_argument("guidelines_json", help="Path to the brand guidelines JSON file")

    reuse = parser.add_argument_group("re-use an existing index (skips upload)")
    reuse.add_argument(
        "--index-id",
        metavar="INDEX_ID",
        help="Use an existing TwelveLabs index instead of creating a new one",
    )
    reuse.add_argument(
        "--video-id",
        metavar="VIDEO_ID",
        help="Use an already-indexed video ID (requires --index-id)",
    )

    return parser.parse_args()


def load_guidelines(path: str) -> Guidelines:
    guidelines_path = Path(path)
    if not guidelines_path.exists():
        print(f"Error: Guidelines file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with guidelines_path.open() as f:
            data = json.load(f)
        return Guidelines.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error: Invalid guidelines JSON — {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()

    # --- Load guidelines ---
    guidelines = load_guidelines(args.guidelines_json)
    brand_name = args.brand_name or guidelines.brand_name

    print(f"\nBrand Compliance Analyser")
    print(f"Brand    : {brand_name}")
    print(f"Video    : {args.video_path}")
    print(f"Rules    : {len(guidelines.rules)} guideline(s) loaded")
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
        # Create a fresh index named after the brand (sanitised)
        index_name = brand_name.lower().replace(" ", "_") + "_compliance"
        print(f"Creating new index: {index_name}")
        index_id = create_index(index_name)
        print(f"Index created: {index_id}")
        video_id = upload_video(index_id, args.video_path)

    # --- Analysis ---
    print(f"\nRunning compliance analysis ({len(guidelines.rules)} rule(s))...")
    violations = analyze_brand_compliance(
        index_id=index_id,
        video_id=video_id,
        brand_name=brand_name,
        rules=guidelines.rules,
    )

    # --- Report ---
    report = ComplianceReport(
        brand=brand_name,
        video_path=args.video_path,
        index_id=index_id,
        video_id=video_id,
        violations=violations,
    )
    print_report(report)

    # Exit with non-zero code if critical violations found (useful for CI pipelines)
    if report.critical_count > 0:
        sys.exit(2)
    elif not report.is_compliant:
        sys.exit(1)


if __name__ == "__main__":
    main()
