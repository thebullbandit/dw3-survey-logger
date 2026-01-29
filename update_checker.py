"""
Update Checker (GitHub Releases)
================================

Best-effort, privacy-minimal update check:
- Calls GitHub Releases API for the configured repo (owner/repo)
- Compares latest tag vs local VERSION
- Emits a friendly COMMS message if a newer version is available

No personal data is sent. One HTTP GET to GitHub with a generic User-Agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Callable, Any, Dict
from pathlib import Path
import json
import re
import time
import urllib.request
import urllib.error


@dataclass(frozen=True)
class UpdateInfo:
    latest_tag: str
    html_url: str
    published_at: str | None = None


def _parse_version_tuple(v: str) -> Optional[Tuple[int, ...]]:
    """
    Extract a comparable version tuple from strings like:
      'v0.9.1', '0.9.1 BETA', '2.1.0-DI'
    Returns None if no digits found.
    """
    if not v:
        return None
    m = re.findall(r"\d+", v)
    if not m:
        return None
    # Keep dot-like structure by reading sequential digits; this is "good enough"
    return tuple(int(x) for x in m)


def is_newer(latest: str, current: str) -> bool:
    lt = _parse_version_tuple(latest)
    ct = _parse_version_tuple(current)
    if lt is None or ct is None:
        # Fallback: if strings differ, don't claim newer confidently
        return latest.strip() != current.strip()
    # Compare lexicographically with padding
    n = max(len(lt), len(ct))
    lt_p = lt + (0,) * (n - len(lt))
    ct_p = ct + (0,) * (n - len(ct))
    return lt_p > ct_p


def detect_repo_slug_from_git(start_dir: Path) -> Optional[str]:
    """
    Try to detect GitHub repo slug (owner/repo) from .git/config.
    Works when running from a cloned repo, not from a packaged exe.
    """
    try:
        cur = start_dir.resolve()
        for _ in range(6):  # climb a few levels
            git_cfg = cur / ".git" / "config"
            if git_cfg.exists():
                txt = git_cfg.read_text(encoding="utf-8", errors="ignore")
                # Match typical GitHub remotes:
                #   url = https://github.com/owner/repo.git
                #   url = git@github.com:owner/repo.git
                m = re.search(r"url\s*=\s*(.+)", txt)
                if not m:
                    return None
                url = m.group(1).strip()
                # Normalize
                url = url.replace("git@github.com:", "https://github.com/")
                url = url.replace("ssh://git@github.com/", "https://github.com/")
                mm = re.search(r"github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?$", url)
                if not mm:
                    return None
                return f"{mm.group(1)}/{mm.group(2)}"
            cur = cur.parent
    except Exception:
        return None
    return None


def fetch_latest_release(repo_slug: str, timeout_s: float = 3.5) -> Optional[UpdateInfo]:
    """
    Fetch latest GitHub release for repo_slug ("owner/repo").
    Returns UpdateInfo or None if unavailable.
    """
    if not repo_slug or "/" not in repo_slug:
        return None

    api_url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "DW3-Survey-Logger",
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    except Exception:
        return None

    tag = (data.get("tag_name") or "").strip()
    html_url = (data.get("html_url") or "").strip()
    published_at = data.get("published_at")
    if not tag or not html_url:
        return None
    return UpdateInfo(latest_tag=tag, html_url=html_url, published_at=published_at)


def should_check(settings_path: Path, min_interval_s: float = 24 * 3600) -> bool:
    """
    Rate limit update checks via settings.json:
      - last_update_check: epoch seconds
    """
    try:
        if not settings_path.exists():
            return True
        data = json.loads(settings_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        last = float(data.get("last_update_check", 0) or 0)
        return (time.time() - last) >= min_interval_s
    except Exception:
        return True


def record_check(settings_path: Path, latest_tag: str | None = None) -> None:
    """
    Persist last_update_check and optionally last_seen_latest_tag.
    """
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any]
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        else:
            data = {}
        data["last_update_check"] = int(time.time())
        if latest_tag:
            data["last_seen_latest_tag"] = latest_tag
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        return


def already_notified(settings_path: Path, latest_tag: str) -> bool:
    try:
        if not settings_path.exists():
            return False
        data = json.loads(settings_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        return (data.get("last_notified_latest_tag") or "") == latest_tag
    except Exception:
        return False


def record_notified(settings_path: Path, latest_tag: str) -> None:
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any]
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        else:
            data = {}
        data["last_notified_latest_tag"] = latest_tag
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        return
