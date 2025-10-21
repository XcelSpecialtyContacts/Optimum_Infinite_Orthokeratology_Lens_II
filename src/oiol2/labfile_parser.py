# labfile_parser.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import logging, re, sys

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # fallback for <=3.10

def load_config(cfg_path: str | Path = "config.toml") -> dict:
    p = Path(cfg_path)
    with p.open('rb') as f:
        return tomllib.load(f)

def labfile_path_for_wo(cfg: dict, work_order: str | int) -> Path:
    wo = str(work_order).strip()
    root = Path(cfg["paths"]["labfile_root"])
    prefix = cfg["labfile"].get("prefix", "")
    suffix = cfg["labfile"].get("suffix", "")
    fname = f"{prefix}{wo}{suffix}"
    return root / fname

def parse_lab_file(
    path: Optional[str | Path],
    fields_spec: Dict[str, Dict[str, str]],
    VALUE_COL_START: int = 36,
) -> Dict[str, Dict[str, Any]]:
    """
    Your previously created parser (unchanged logic), kept here for reuse.
    """
    if not path:
        return {}

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Lab File not found: {p}")

    data: Dict[str, Dict[str, Any]] = {
        key: {"title": spec["title"], "seg": spec["seg"], "value": ""}
        for key, spec in fields_spec.items()
    }

    def clean_value(v: str) -> str:
        if not v:
            return ""
        v = v.strip().strip(",;")
        if re.fullmatch(r"\*calculated", v, flags=re.IGNORECASE):
            return ""
        return v

    seg_values: Dict[str, str] = {}
    start_idx = max(0, VALUE_COL_START - 1)
    seg_re = re.compile(r'^\s*([A-Z]?\d{2,3})\b')

    for raw_line in p.read_text(errors="replace").splitlines():
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

def load_lab_data(cfg: dict, work_order: str | int) -> dict:
    labfile = labfile_path_for_wo(cfg, work_order)
    fields_spec = cfg.get("lab_fields", {})
    value_col = int(cfg["labfile"].get("value_col_start", 36))
    return parse_lab_file(labfile, fields_spec, value_col)
