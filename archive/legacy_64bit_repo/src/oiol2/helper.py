"""
oiol2.helper
==============
Helper functions

Author: Allen Gilliard
"""

from __future__ import annotations

from pathlib import Path # Needed for handling OS paths, makes it cleaner
import sys # Access to system-specific parameters and functions
# Add <repo>/src to sys.path so 'oiol2' is importable when running from repo root
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# For parsing TOML files
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

def repo_root_from_this_file() -> Path:
    #
    # Resolve project root assuming this file lives at src/oiol2/main.py.
    # Root = <repo>/
    # 
    here = Path(__file__).resolve()
    # .../src/oiol2/main.py -> .../src -> .../
    return here.parent.parent.parent

def default_config_path() -> Path:
    return repo_root_from_this_file() / "configs" / "config.toml"

def default_lab_spec_path() -> Path:
    return repo_root_from_this_file() / "configs" / "lab_file.toml"

def ensure_labfile_importable() -> None:
    #
    # Make the repo root importable so `import labfile` works when running as a module.
    #
    root = str(repo_root_from_this_file())
    if root not in sys.path:
        sys.path.insert(0, root)

def default_logs_dir() -> Path:
    return repo_root_from_this_file() / "logs"

def ensure_dirs(cfg: AppConfig) -> None:
    #
    # Create any required directories if they don't exist (e.g., output dir, logs dir).
    #
    cfg.output.dir.mkdir(parents=True, exist_ok=True)
    default_logs_dir().mkdir(parents=True, exist_ok=True)

def default_design_path() -> Path:
    return repo_root_from_this_file() / "data" / "lens_design.toml"

def load_toml_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)

def load_toml(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as f:
        return tomllib.load(f)

def _expand_pathlike(v: Any) -> Path:
    """
    Expand env vars and ~ and return a Path. Accepts str or Path.
    """
    if isinstance(v, Path):
        s = str(v)
    else:
        s = str(v)
    s = Path(s).expanduser()
    # Expand any %VAR% (Windows) or $VAR (POSIX) via os.path.expandvars
    import os
    s = os.path.expandvars(str(s))
    return Path(s)

def _coerce_float(name: str, v: Any) -> float:
    try:
        return float(v)
    except Exception as e:
        raise ValueError(f"Expected a number for '{name}', got {v!r}") from e

def summarize_lab_result(d: dict[str, Any]) -> str:
    keys = ["BC", "Dia", "Power"]
    lines = ["=== Loaded Lab File (selected fields) ==="]
    for k in keys:
        if k in d:
            lines.append(f"{k}: {d[k]}")
    if len(lines) == 1:
        lines.append("(no standard keys found; loaded dictionary keys: " + ", ".join(sorted(d.keys())) + ")")
    lines.append("=========================================")
    return "\n".join(lines)