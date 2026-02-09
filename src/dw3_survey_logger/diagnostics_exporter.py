
"""Diagnostics Exporter

Creates a ZIP bundle that helps debug user issues.

Contents (best effort):
- manifest.json (app version, platform, key config, basic stats)
- bootstrap_settings.json (user settings) if present
- logger.log (main logfile) if present
- comms_tail.txt (latest COMMS messages)
- db/ (Earth2 + Observations DB files, plus -wal/-shm if present) [optional]
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import logging
logger = logging.getLogger("dw3.diagnostics_exporter")


def _redact_path(p: str) -> str:
    """Replace the user's home directory prefix with <HOME> for safer sharing."""
    try:
        home = str(Path.home())
        return p.replace(home, "<HOME>")
    except Exception as e:
        logger.debug("_redact_path failed: %s", e)
        return p


def _copy_if_exists(src: Path, dst: Path) -> bool:
    try:
        if src and src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True
    except Exception as e:
        logger.debug("_copy_if_exists failed for %s: %s", src, e)
        pass
    return False


def export_diagnostics_zip(
    zip_path: Path,
    config: Dict[str, Any],
    model: Any = None,
    include_db: bool = True,
) -> Path:
    zip_path = Path(zip_path)

    tmpdir = Path(tempfile.mkdtemp(prefix="dw3_diag_"))
    try:
        # ------------------------------------------------------------------
        # Manifest
        # ------------------------------------------------------------------
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest: Dict[str, Any] = {
            "generated_utc": now,
            "app_name": str(config.get("APP_NAME", "")),
            "app_version": str(config.get("VERSION", "")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cwd": _redact_path(os.getcwd()),
            "paths": {
                "outdir": _redact_path(str(config.get("OUTDIR", ""))),
                "export_dir": _redact_path(str(config.get("EXPORT_DIR", ""))),
                "journal_dir": _redact_path(str(config.get("JOURNAL_DIR", ""))),
                "db_path": _redact_path(str(config.get("DB_PATH", ""))),
                "observer_db_path": _redact_path(str(Path(config.get("OUTDIR", "")) / "DW3_Earth2_Observations.db")),
                "logfile": _redact_path(str(config.get("LOGFILE", ""))),
                "bootstrap_settings": _redact_path(str(config.get("BOOTSTRAP_SETTINGS_PATH", ""))),
            },
            "settings": {
                "ui_refresh_fast_ms": config.get("UI_REFRESH_FAST_MS"),
                "ui_refresh_slow_ms": config.get("UI_REFRESH_SLOW_MS"),
                "comms_max_lines": config.get("COMMS_MAX_LINES"),
                "hotkey_label": config.get("HOTKEY_LABEL"),
                "test_mode": config.get("TEST_MODE"),
            },
            "stats": {},
            "notes": [
                "Paths are redacted to <HOME> for safer sharing.",
                "If include_db was false, no database files were bundled.",
            ],
        }

        if model is not None:
            try:
                manifest["stats"] = model.get_stats() or {}
            except Exception as e:
                logger.debug("Failed to get model stats: %s", e)
                manifest["stats"] = {}
            try:
                # Snapshot a few status fields (avoid huge dumps)
                status = model.get_status() or {}
                if isinstance(status, dict):
                    manifest["status"] = {
                        "session_id": status.get("session_id", ""),
                        "last_system": status.get("last_system", ""),
                        "last_body": status.get("last_body", ""),
                        "last_type": status.get("last_type", ""),
                        "last_rating": status.get("last_rating", ""),
                    }
            except Exception as e:
                logger.debug("Failed to get model status: %s", e)

        (tmpdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # ------------------------------------------------------------------
        # Files
        # ------------------------------------------------------------------
        # Bootstrap settings
        bs_path = Path(config.get("BOOTSTRAP_SETTINGS_PATH", "") or "")
        _copy_if_exists(bs_path, tmpdir / "bootstrap_settings.json")

        # Log file
        log_path = Path(config.get("LOGFILE", "") or "")
        _copy_if_exists(log_path, tmpdir / "logger.log")

        # COMMS tail
        try:
            if model is not None:
                msgs = model.get_comms_messages() or []
                tail = "\n".join(str(m) for m in msgs[-200:])
                (tmpdir / "comms_tail.txt").write_text(tail, encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to write comms_tail: %s", e)

        # DB files (optional)
        if include_db:
            outdir = Path(config.get("OUTDIR", "") or "")
            db_paths = []
            try:
                db_paths.append(Path(config.get("DB_PATH", "") or ""))
            except Exception as e:
                logger.debug("Failed to resolve DB_PATH: %s", e)
            try:
                db_paths.append(outdir / "DW3_Earth2_Observations.db")
            except Exception as e:
                logger.debug("Failed to resolve observer DB path: %s", e)

            for p in db_paths:
                if not p:
                    continue
                p = Path(p)
                if not p.exists():
                    continue
                _copy_if_exists(p, tmpdir / "db" / p.name)
                # Include WAL/SHM if present
                _copy_if_exists(Path(str(p) + "-wal"), tmpdir / "db" / (p.name + "-wal"))
                _copy_if_exists(Path(str(p) + "-shm"), tmpdir / "db" / (p.name + "-shm"))

        # ------------------------------------------------------------------
        # Zip it up
        # ------------------------------------------------------------------
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in tmpdir.rglob("*"):
                if file.is_file():
                    zf.write(file, arcname=str(file.relative_to(tmpdir)))

        return zip_path

    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            logger.debug("Failed to clean up tmpdir: %s", e)
