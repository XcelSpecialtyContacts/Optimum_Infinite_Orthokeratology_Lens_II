from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any

# Python 3.11+: stdlib tomllib; fallback to tomli if needed.
try:
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

try:
    import tomli  # type: ignore
except Exception:  # pragma: no cover
    tomli = None  # type: ignore


@dataclass(frozen=True)
class LabField:
    seg: str
    title: str


LabFieldsSpec = Dict[str, LabField]


def _load_toml_bytes(p: Path) -> dict:
    data = p.read_bytes()
    if tomllib is not None:
        return tomllib.loads(data.decode("utf-8"))
    if tomli is not None:
        return tomli.loads(data.decode("utf-8"))
    raise RuntimeError(
        "No TOML parser available. On Python 3.11+, tomllib should exist. "
        "Otherwise, install `tomli`."
    )


def load_lab_fields(toml_path: str | Path) -> LabFieldsSpec:
    """
    Load lab field spec from TOML like:

      [lab_fields.BC]
      seg = '060'
      title = 'Base Curve'

    Returns: dict[str, LabField]
    """
    p = Path(toml_path)
    if not p.exists():
        raise FileNotFoundError(f"TOML not found: {p}")

    raw = _load_toml_bytes(p)

    fields: LabFieldsSpec = {}
    lab_fields: Optional[Dict[str, Any]] = raw.get("lab_fields", None)
    if not isinstance(lab_fields, dict):
        raise ValueError("Expected [lab_fields.*] sections in TOML")

    for key, section in lab_fields.items():
        if not isinstance(section, dict):
            continue
        seg = str(section.get("seg", "")).strip()
        title = str(section.get("title", "")).strip()
        if not seg or not title:
            raise ValueError(f"lab_fields.{key} must define non-empty 'seg' and 'title'")
        fields[key] = LabField(seg=seg, title=title)

    return fields
