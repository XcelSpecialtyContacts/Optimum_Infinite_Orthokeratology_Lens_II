from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

from .config import LabFieldsSpec


def parse_lab_file(
    path: Optional[str | Path],
    fields_spec: LabFieldsSpec,
    VALUE_COL_START: int = 36,  # 1-based column where the value starts
) -> Dict[str, Dict[str, Any]]:
    """
    Parse a Lab File and return a dict keyed by field name (e.g., 'BC', 'Dia', ...),
    each value is {"title": str, "seg": str, "value": str} based on fields_spec.

    Rules:
      - The value field is fixed-width and begins at column VALUE_COL_START (default 36).
      - If a segment has no value (blank past col 36) OR the value is "*Calculated" (any case), store "".
    """
    if not path:
        return {}

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Lab File not found: {p}")

    # initialize output structure from spec
    data: Dict[str, Dict[str, Any]] = {
        key: {"title": field.title, "seg": field.seg, "value": ""}
        for key, field in fields_spec.items()
    }

    def clean_value(v: str) -> str:
        if not v:
            return ""
        v = v.strip().strip(",;")
        if re.fullmatch(r"\*calculated", v, flags=re.IGNORECASE):
            return ""
        return v

    seg_values: Dict[str, str] = {}
    start_idx = max(0, VALUE_COL_START - 1)  # convert to 0-based
    seg_re = re.compile(r"^\s*([A-Z]?\d{2,3})\b")  # e.g., "007", "060", "A10"

    # robust file read
    text = p.read_text(encoding="utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n\r")
        m = seg_re.match(line)
        if not m:
            continue
        code = m.group(1)
        value_field = line[start_idx:] if len(line) >= VALUE_COL_START else ""
        value = clean_value(value_field)
        seg_values[code] = value

    for key, entry in data.items():
        seg = entry["seg"]
        if seg in seg_values:
            entry["value"] = clean_value(seg_values.get(seg, ""))

    logging.info("Loaded Lab File: %s", p)
    return data


# --- Optional: tiny CLI for quick checks ---
def _cli() -> None:  # pragma: no cover
    import argparse
    import json
    from .config import load_lab_fields

    ap = argparse.ArgumentParser(description="Parse a Lab File using TOML field map.")
    ap.add_argument("--lab", required=True, help="Path to the Lab File")
    ap.add_argument("--fields", required=True, help="Path to lab_field TOML")
    ap.add_argument("--col-start", type=int, default=36, help="1-based start column for value")
    args = ap.parse_args()

    spec = load_lab_fields(args.fields)
    result = parse_lab_file(args.lab, spec, VALUE_COL_START=args.col_start)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    _cli()
