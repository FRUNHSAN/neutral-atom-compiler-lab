"""
stale_snapshot.py — .stale.json time-series archiving.

Write current verification-stack snapshot to .stale.json.
Archive historical snapshots to .stale_history/ for flickering detection.

Retention: max 1 snapshot per day, auto-clean after 30 days.

Usage:
  python framework/stale_snapshot.py .                    # write snapshot
  python framework/stale_snapshot.py . --json-only        # skip archiving
"""
from __future__ import annotations
import json
import os
import sys
import subprocess
from datetime import datetime, timezone


def get_git_head(project_root: str) -> str:
    """Get short HEAD commit hash."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root, encoding="utf-8",
        ).strip()
    except Exception:
        return "unknown"


def collect_snapshot(project_root: str) -> dict:
    """Collect current verification-stack state.

    Returns a dict with:
      - timestamp (ISO 8601)
      - head: git commit hash
      - layers: per-layer state (presence checks — does tool output exist?)
      - file_hashes: quick freshness comparison via mtime
    """
    head = get_git_head(project_root)
    now = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "timestamp": now,
        "head": head,
        "layers": {},
    }

    # L4: SMT verification reports
    smt_path = os.path.join(project_root, ".smt_report.json")
    snapshot["layers"]["SMT"] = {
        "present": os.path.exists(smt_path),
        "mtime": os.path.getmtime(smt_path) if os.path.exists(smt_path) else None,
    }

    # L5: CFG verification reports
    cfg_path = os.path.join(project_root, ".cfg_report.json")
    snapshot["layers"]["CFG"] = {
        "present": os.path.exists(cfg_path),
        "mtime": os.path.getmtime(cfg_path) if os.path.exists(cfg_path) else None,
    }

    # L3: @effect report
    effect_path = os.path.join(project_root, ".effect_report.json")
    snapshot["layers"]["effect"] = {
        "present": os.path.exists(effect_path),
        "mtime": os.path.getmtime(effect_path) if os.path.exists(effect_path) else None,
    }

    # L1: check-consistency output
    # (check.py doesn't write a file — skip, or capture last run timestamp)

    # Per-path density snapshot (if available)
    per_path_path = os.path.join(project_root, ".per_path_density.json")
    if os.path.exists(per_path_path):
        with open(per_path_path, encoding="utf-8") as f:
            snapshot["per_path"] = json.load(f)

    return snapshot


def save_snapshot(project_root: str, snapshot: dict) -> str:
    """Write .stale.json. Returns path."""
    path = os.path.join(project_root, ".stale.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return path


def archive_snapshot(project_root: str, snapshot: dict) -> str | None:
    """Archive snapshot to .stale_history/.

    Dedup: same calendar day → overwrite previous.
    Returns archive path, or None if skipped.
    """
    history_dir = os.path.join(project_root, ".stale_history")
    os.makedirs(history_dir, exist_ok=True)

    # Calendar day as key (UTC)
    ts = datetime.fromisoformat(snapshot["timestamp"])
    day_key = ts.strftime("%Y-%m-%d")
    archive_path = os.path.join(history_dir, f"stale_{day_key}.json")

    # Check if today already has a snapshot
    if os.path.exists(archive_path):
        existing_mtime = os.path.getmtime(archive_path)
        # Overwrite if existing is from earlier today (same day, different time)
        # This gives us "latest snapshot of the day"
        pass  # Always overwrite — keep latest of the day

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return archive_path


def cleanup_history(project_root: str, max_days: int = 30) -> int:
    """Remove snapshots older than max_days. Returns count removed."""
    history_dir = os.path.join(project_root, ".stale_history")
    if not os.path.isdir(history_dir):
        return 0

    now = datetime.now(timezone.utc)
    removed = 0
    for fname in os.listdir(history_dir):
        if not fname.startswith("stale_") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(history_dir, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
            if (now - mtime).days > max_days:
                os.remove(fpath)
                removed += 1
        except OSError:
            pass
    return removed


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Write .stale.json snapshot and archive to .stale_history/"
    )
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("--json-only", action="store_true",
                        help="Only write .stale.json, skip archiving")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="Skip auto-cleanup of old snapshots")
    args = parser.parse_args()

    root = args.project_root
    snapshot = collect_snapshot(root)

    stale_path = save_snapshot(root, snapshot)
    print(f"  [stale] .stale.json written: {snapshot['head']} @ {snapshot['timestamp']}")

    if not args.json_only:
        archive_path = archive_snapshot(root, snapshot)
        if archive_path:
            print(f"  [stale] archived: {os.path.basename(archive_path)}")

        if not args.no_cleanup:
            removed = cleanup_history(root)
            if removed:
                print(f"  [stale] cleaned: {removed} snapshots >30 days removed")

    # Print per-layer freshness summary
    layers = snapshot.get("layers", {})
    head = snapshot["head"]
    for name, info in sorted(layers.items()):
        if info["present"]:
            print(f"  [stale]   {name}: present")
        else:
            print(f"  [stale]   {name}: absent")


if __name__ == "__main__":
    main()
