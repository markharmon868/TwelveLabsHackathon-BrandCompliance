"""Terminal report formatter for compliance results."""

from .models import Appearance, ComplianceReport, Violation

_RED    = "\033[91m"
_YELLOW = "\033[93m"
_GREEN  = "\033[92m"
_CYAN   = "\033[96m"
_GRAY   = "\033[37m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"

_SEVERITY_COLOR = {"critical": _RED, "moderate": _YELLOW, "minor": _CYAN}
_SEVERITY_BADGE = {
    "critical": f"{_RED}{_BOLD}[CRITICAL]{_RESET}",
    "moderate": f"{_YELLOW}{_BOLD}[MODERATE]{_RESET}",
    "minor":    f"{_CYAN}[MINOR]{_RESET}",
}
_STATUS_BADGE = {
    "COMPLIANT":      f"{_GREEN}{_BOLD}✓ COMPLIANT{_RESET}",
    "VIOLATION":      f"{_RED}{_BOLD}✗ VIOLATION{_RESET}",
    "UNDER-DELIVERED": f"{_YELLOW}{_BOLD}⚠ UNDER-DELIVERED{_RESET}",
}


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds % 60
    return f"{m}:{s:05.2f}"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds)//60}m {seconds%60:.0f}s"


def print_report(report: ComplianceReport) -> None:
    W = 72
    div = "─" * W

    print()
    print(f"{_BOLD}{'═' * W}{_RESET}")
    print(f"{_BOLD}  BRAND INTEGRATION AUDIT REPORT{_RESET}")
    print(f"{'═' * W}")
    print(f"  Brand      : {_BOLD}{report.brand}{_RESET}")
    print(f"  Video      : {report.video_path}")
    print(f"  Index ID   : {_DIM}{report.index_id}{_RESET}")
    print(f"  Video ID   : {_DIM}{report.video_id}{_RESET}")
    print(div)

    # --- Delivery summary ---
    status_badge = _STATUS_BADGE[report.delivery_status]
    print(f"\n  Overall Status : {status_badge}")
    print()

    contracted = report.contracted_screen_time_seconds
    delivered  = report.delivered_screen_time_seconds
    if contracted > 0:
        pct = delivered / contracted * 100
        bar = _progress_bar(min(pct, 100), width=30)
        print(f"  Screen Time    : {bar}  {_fmt_duration(delivered)} of {_fmt_duration(contracted)} contracted ({pct:.0f}%)")
        if report.is_under_delivered:
            print(f"  {_YELLOW}⚠ Under-delivered by {_fmt_duration(report.screen_time_gap_seconds)}{_RESET}")
    print()

    # --- Appearance counts ---
    total = len(report.appearances)
    print(f"  Appearances    : {total} total  "
          f"({_GREEN}{report.compliant_count} clean{_RESET} / "
          f"{_RED}{len(report.violations)} violation(s){_RESET} / "
          f"{_GRAY}{report.needs_review_count} needs review{_RESET})")
    print()

    # --- Violations ---
    if report.violations:
        print(f"  {div}")
        print(f"  {_RED}{_BOLD}VIOLATIONS ({len(report.violations)}){_RESET}")
        print(f"  {div}")
        for i, v in enumerate(report.violations, 1):
            badge = _SEVERITY_BADGE[v.severity]
            color = _SEVERITY_COLOR[v.severity]
            print(f"\n  {color}{_BOLD}Violation #{i}{_RESET}  {badge}")
            print(f"  Timestamp  : {_fmt_time(v.timestamp_start)} → {_fmt_time(v.timestamp_end)}")
            print(f"  Context    : {v.prohibited_context}")
            print(f"  Confidence : {v.confidence:.0%}")
            print(f"  Details    : {_wrap(v.explanation, width=W - 13, indent=13)}")
        print()

    # --- All appearances (compact) ---
    if report.appearances:
        print(f"  {div}")
        print(f"  {'APPEARANCE TIMELINE':}")
        print(f"  {div}")
        print(f"  {'#':>3}  {'TIME':>10}  {'DUR':>6}  {'STATUS':<14}  {'CONF':>5}  NOTES")
        print(f"  {'─'*3}  {'─'*10}  {'─'*6}  {'─'*14}  {'─'*5}  {'─'*25}")
        for i, a in enumerate(report.appearances, 1):
            status_str, color = _appearance_fmt(a)
            note = a.explanation[:40] + "…" if len(a.explanation) > 40 else a.explanation
            timerange = f"{_fmt_time(a.timestamp_start)}→{_fmt_time(a.timestamp_end)}"
            print(f"  {i:>3}  {timerange:>10}  {_fmt_duration(a.duration):>6}  "
                  f"{color}{status_str:<14}{_RESET}  {a.confidence:>4.0%}  {_DIM}{note}{_RESET}")
        print()

    print(f"{'═' * W}\n")


def _appearance_fmt(a: Appearance) -> tuple[str, str]:
    if a.status == "compliant":
        return "COMPLIANT", _GREEN
    if a.status == "violation":
        return "VIOLATION", _RED
    return "NEEDS REVIEW", _GRAY


def _progress_bar(pct: float, width: int = 30) -> str:
    filled = int(width * pct / 100)
    color = _GREEN if pct >= 100 else (_YELLOW if pct >= 50 else _RED)
    bar = "█" * filled + "░" * (width - filled)
    return f"{color}[{bar}]{_RESET}"


def _wrap(text: str, width: int, indent: int) -> str:
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
