"""Terminal report formatter for compliance results."""

from .models import ComplianceReport, Violation

# ANSI color codes
_RED = "\033[91m"
_YELLOW = "\033[93m"
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_SEVERITY_COLOR = {
    "critical": _RED,
    "moderate": _YELLOW,
    "minor": _CYAN,
}

_SEVERITY_BADGE = {
    "critical": f"{_RED}{_BOLD}[CRITICAL]{_RESET}",
    "moderate": f"{_YELLOW}{_BOLD}[MODERATE]{_RESET}",
    "minor": f"{_CYAN}[MINOR]{_RESET}",
}


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds % 60
    return f"{m}:{s:05.2f}"


def print_report(report: ComplianceReport) -> None:
    width = 72
    divider = "─" * width

    print()
    print(f"{_BOLD}{'═' * width}{_RESET}")
    print(f"{_BOLD}  BRAND COMPLIANCE REPORT{_RESET}")
    print(f"{'═' * width}")
    print(f"  Brand      : {_BOLD}{report.brand}{_RESET}")
    print(f"  Video      : {report.video_path}")
    print(f"  Index ID   : {_DIM}{report.index_id}{_RESET}")
    print(f"  Video ID   : {_DIM}{report.video_id}{_RESET}")
    print(divider)

    if report.is_compliant:
        print(f"\n  {_GREEN}{_BOLD}✓ No violations detected. Video is compliant.{_RESET}\n")
    else:
        total = len(report.violations)
        print(
            f"\n  {_RED}{_BOLD}✗ {total} violation(s) found{_RESET}  "
            f"({_RED}{report.critical_count} critical{_RESET} / "
            f"{_YELLOW}{report.moderate_count} moderate{_RESET} / "
            f"{_CYAN}{report.minor_count} minor{_RESET})\n"
        )

        for i, v in enumerate(report.violations, 1):
            badge = _SEVERITY_BADGE[v.severity]
            color = _SEVERITY_COLOR[v.severity]
            print(f"  {color}{_BOLD}Violation #{i}{_RESET}  {badge}")
            print(f"  {divider}")
            print(f"  Timestamp  : {_fmt_time(v.timestamp_start)} → {_fmt_time(v.timestamp_end)}")
            print(f"  Brand      : {v.brand}")
            print(f"  Context    : {v.prohibited_context}")
            print(f"  Confidence : {v.confidence:.0%}")
            print(f"  Details    : {_wrap(v.explanation, width=width - 13, indent=13)}")
            print()

    print(f"{'═' * width}\n")


def _wrap(text: str, width: int, indent: int) -> str:
    """Simple word-wrap with hanging indent for subsequent lines."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).lstrip()
    if current:
        lines.append(current)
    pad = " " * indent
    return ("\n" + pad).join(lines)
