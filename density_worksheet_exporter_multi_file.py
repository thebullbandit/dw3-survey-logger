"""
Density Worksheet Exporter - Multi-File Version
================================================

Creates separate DW3 "Stellar Density Scan Worksheet" Excel files for each sample.
Each sample (1000ly span with ~20 systems) gets its own .xlsx file.

Modified from original to support:
- One .xlsx file per sample_index
- Files named like "DW3_Stellar_Density_CMDR_Sample_01.xlsx"
- Preserves all original functionality per file
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Dict, Any, List
from collections import defaultdict

import sys
import openpyxl
import re


def resource_path(*parts: str) -> Path:
    """
    Returns an absolute Path to a bundled resource.
    Works for: PyInstaller onefile + normal python runs.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)


template_path = resource_path("templates", "Stellar Density Scan Worksheet.xlsx")


def _safe_parse_iso(ts: str) -> Optional[datetime]:
    try:
        # Handles both "...Z" and "+00:00"
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def export_density_worksheet_from_notes_multi_file(
    notes: Iterable[Any],
    template_path: Path,
    output_path: Path,
    cmdr_name: str = "UnknownCMDR",
    sample_tag: str = "",
    z_bin: Optional[int] = None,
    sheet_name: str = "Blank CW",
) -> List[Path]:

    template_path = resource_path("templates", "Stellar Density Scan Worksheet.xlsx")
    output_path = Path(output_path)
    _cmdr = cmdr_name

    # Normalize notes into dicts
    normalized: List[Dict[str, Any]] = []
    for n in notes:
        if n is None:
            continue
        if isinstance(n, dict):
            d = n
        else:
            try:
                d = asdict(n)
            except Exception:
                d = dict(n)
        normalized.append(d)

    # Filter to valid density rows
    all_rows: List[Dict[str, Any]] = []
    for d in normalized:
        if not (d.get("system_name") or ""):
            continue
        if d.get("max_distance") is None:
            continue
        rs = str(d.get("record_status", "")).lower()
        if rs in ("amended", "deleted", "inactive"):
            continue
        all_rows.append(d)

    if not all_rows:
        raise ValueError(
            "No completed samples to export. Save at least one observation with density data before exporting."
        )

    # Group rows by sample_index
    samples_dict: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        try:
            samples_dict[int(row.get("sample_index"))].append(row)
        except Exception:
            pass

    if not samples_dict:
        raise ValueError("No valid sample_index found in data. Cannot group samples.")

    created_files: List[Path] = []

    safe_cmdr = re.sub(r"[^A-Za-z0-9_-]", "_", (_cmdr or "UnknownCMDR"))
    z_part = f"_Z{int(z_bin)}" if z_bin is not None else ""

    base_dir = output_path.parent if output_path.suffix.lower() == ".xlsx" else output_path
    base_dir.mkdir(parents=True, exist_ok=True)

    for sample_idx in sorted(samples_dict.keys()):
        rows = samples_dict[sample_idx]

        # Sort rows by timestamp + system_index
        def sort_key(d: Dict[str, Any]):
            ts = _safe_parse_iso(str(d.get("timestamp_utc") or ""))
            try:
                si = int(d.get("system_index") or 0)
            except Exception:
                si = 0
            return (ts or datetime.min, si)

        rows.sort(key=sort_key)

        wb = openpyxl.load_workbook(template_path)
        ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb[wb.sheetnames[0]]

        START_ROW = 6

        # 🔒 Static Z Sample column (B): 0..1000 step 50
        static_z = list(range(0, 1001, 50))
        for i, z in enumerate(static_z):
            ws.cell(START_ROW + i, 2).value = z

        # Header: CMDR name and date
        ws["A1"].value = f"CMDR {_cmdr or 'UnknownCMDR'} - DW3 Stellar Density Scans"
        if rows:
            dt = _safe_parse_iso(str(rows[0].get("timestamp_utc") or ""))
            if dt:
                ws["B2"].value = dt.date().isoformat()

        # Write data rows
        for i, d in enumerate(rows):
            r = START_ROW + i

            ws.cell(r, 1).value = d.get("system_name") or ""     # A System
            # Column B intentionally NOT written (static Z values)

            ws.cell(r, 3).value = d.get("system_count")         # C System Count

            corrected = d.get("corrected_n")
            if corrected is None:
                sc = d.get("system_count")
                corrected = (sc + 1) if sc is not None else None
            if corrected is not None:
                ws.cell(r, 4).value = corrected                 # D Corrected n

            ws.cell(r, 5).value = d.get("max_distance")         # E Max Distance

            sp = d.get("star_pos") or (None, None, None)
            try:
                x, y, z = sp
            except Exception:
                x = y = z = None

            ws.cell(r, 7).value = x                              # G X
            ws.cell(r, 8).value = y                              # H Y
            ws.cell(r, 9).value = z                              # I Z

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"DW3_Stellar_Density_{safe_cmdr}{z_part}_Sample_{sample_idx:02d}_{ts}.xlsx"
        file_path = base_dir / filename

        wb.save(file_path)
        created_files.append(file_path)

    return created_files

