# src/oiol2/main.py
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

# Load modules specific to this project
from oiol2.vis.plotting import plot_meridional_curves, Curve
from oiol2.geometry.meridional import generate_optic_zone_meridional

# -----------------------
# Data models (typed)
# -----------------------

@dataclass(frozen=True)
class PathsCfg:
    labfile_root: Path

@dataclass(frozen=True)
class OutputCfg:
    dir: Path
    file_stem_pattern: str
    point_format: str
    header: str
    footer: str

@dataclass(frozen=True)
class XcelPointfileParmsCfg:
    point_spacing_mm: float
    meridians: int

@dataclass(frozen=True)
class XcelOptionsCfg:
    use_vertex_code_from_lab: bool
    vertex_code: int

@dataclass(frozen=True)
class AppConfig:
    paths: PathsCfg
    output: OutputCfg
    xcel_pointfile_parms: XcelPointfileParmsCfg
    xcel_options: XcelOptionsCfg

@dataclass(frozen=True)
class ParamSpec:
    units: str
    default: float
    min: float
    max: float
    step: float

@dataclass(frozen=True)
class LensDesign:
    meta: Mapping[str, Any]
    # map of "section.param" -> ParamSpec (e.g., "landing_zone.angle")
    params: Mapping[str, ParamSpec]

# -----------------------
# Helpers
# -----------------------

def repo_root_from_this_file() -> Path:
    """
    Resolve project root assuming this file lives at src/oiol2/main.py.
    Root = <repo>/
    """
    here = Path(__file__).resolve()
    # .../src/oiol2/main.py -> .../src -> .../
    return here.parent.parent.parent


def default_config_path() -> Path:
    return repo_root_from_this_file() / "configs" / "config.toml"

def default_lab_spec_path() -> Path:
    return repo_root_from_this_file() / "configs" / "lab_file.toml"

def ensure_labfile_importable() -> None:
    """
    Make the repo root importable so `import labfile` works when running as a module.
    """
    root = str(repo_root_from_this_file())
    if root not in sys.path:
        sys.path.insert(0, root)

def default_logs_dir() -> Path:
    return repo_root_from_this_file() / "logs"

def ensure_dirs(cfg: AppConfig) -> None:
    """
    Create any required directories if they don't exist (e.g., output dir, logs dir).
    """
    cfg.output.dir.mkdir(parents=True, exist_ok=True)
    default_logs_dir().mkdir(parents=True, exist_ok=True)

def default_design_path() -> Path:
    return repo_root_from_this_file() / "data" / "lens_design.toml"

def load_toml_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
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

def load_toml(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as f:
        return tomllib.load(f)


def validate_and_build(cfg: dict[str, Any]) -> AppConfig:
    # --- [paths] ---
    try:
        paths_section = cfg["paths"]
        labfile_root = _expand_pathlike(paths_section["labfile_root"])
    except KeyError as e:
        raise KeyError(f"Missing required key in [paths]: {e}")

    # --- [output] ---
    try:
        output_section = cfg["output"]
        out_dir = _expand_pathlike(output_section["dir"])
        file_stem_pattern = str(output_section["file_stem_pattern"])
        point_format = str(output_section["point_format"])
        header = str(output_section.get("header", ""))
        footer = str(output_section.get("footer", ""))
    except KeyError as e:
        raise KeyError(f"Missing required key in [output]: {e}")

    # Helper to read either nested or flat dotted keys
    def get_section(*keys: str) -> dict[str, Any]:
        # Try nested: cfg[keys[0]][keys[1]]...
        cur: Any = cfg
        try:
            for k in keys:
                cur = cur[k]
            if isinstance(cur, dict):
                return cur
        except KeyError:
            pass
        # Fallback to flat dotted key for backward compatibility
        flat = ".".join(keys)
        if flat in cfg and isinstance(cfg[flat], dict):
            return cfg[flat]
        raise KeyError(flat)

    # --- [xcel.pointfile_parms] ---
    try:
        xcel_pf = get_section("xcel", "pointfile_parms")
        point_spacing_mm = float(xcel_pf["point_spacing_mm"])
        meridians = int(xcel_pf["meridians"])
    except KeyError as e:
        raise KeyError(f"Missing required key in [xcel.pointfile_parms]: {e}")

    # --- [xcel.options] ---
    try:
        xcel_opt = get_section("xcel", "options")
        use_vertex_code_from_lab = bool(xcel_opt["use_vertex_code_from_lab"])
        vertex_code = int(xcel_opt["vertex_code"])
    except KeyError as e:
        raise KeyError(f"Missing required key in [xcel.options]: {e}")

    # Basic validations
    if point_spacing_mm <= 0:
        raise ValueError("[xcel.pointfile_parms].point_spacing_mm must be > 0")
    if meridians <= 0:
        raise ValueError("[xcel.pointfile_parms].meridians must be > 0")

    return AppConfig(
        paths=PathsCfg(labfile_root=labfile_root),
        output=OutputCfg(
            dir=out_dir,
            file_stem_pattern=file_stem_pattern,
            point_format=point_format,
            header=header,
            footer=footer,
        ),
        xcel_pointfile_parms=XcelPointfileParmsCfg(
            point_spacing_mm=point_spacing_mm, meridians=meridians
        ),
        xcel_options=XcelOptionsCfg(
            use_vertex_code_from_lab=use_vertex_code_from_lab,
            vertex_code=vertex_code,
        ),
    )

def _coerce_float(name: str, v: Any) -> float:
    try:
        return float(v)
    except Exception as e:
        raise ValueError(f"Expected a number for '{name}', got {v!r}") from e

def _parse_param_block(path_key: str, block: dict[str, Any]) -> ParamSpec:
    # Required keys with simple coercion
    try:
        units = str(block["units"])
        default = _coerce_float(path_key + ".default", block["default"])
        vmin = _coerce_float(path_key + ".min", block["min"])
        vmax = _coerce_float(path_key + ".max", block["max"])
        step = _coerce_float(path_key + ".step", block["step"])
    except KeyError as e:
        raise KeyError(f"Missing key {e} under [{path_key}]")

    # Basic sanity
    if vmax < vmin:
        raise ValueError(f"[{path_key}] max {vmax} < min {vmin}")
    if step < 0:
        raise ValueError(f"[{path_key}] step must be >= 0")
    if not (vmin <= default <= vmax):
        # allow pinning when min==max==default, but fail on out-of-range defaults
        raise ValueError(f"[{path_key}] default {default} not in [{vmin}, {vmax}]")

    return ParamSpec(units=units, default=default, min=vmin, max=vmax, step=step)

def load_lens_design(design_path: Path) -> LensDesign:
    raw = load_toml_file(design_path)

    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("[meta] must be a table")

    params: dict[str, ParamSpec] = {}
    for top_key, top_val in raw.items():
        if top_key == "meta":
            continue
        if not isinstance(top_val, dict):
            # each non-meta key should be a table (e.g., [landing_zone], [optics])
            raise ValueError(f"[{top_key}] must be a table")
        for sub_key, sub_val in top_val.items():
            # each child should be a param table holding units/default/min/max/step
            if not isinstance(sub_val, dict):
                raise ValueError(f"[{top_key}.{sub_key}] must be a table")
            path_key = f"{top_key}.{sub_key}"
            params[path_key] = _parse_param_block(path_key, sub_val)

    return LensDesign(meta=meta, params=params)

def setup_logging() -> None:
    log_path = default_logs_dir() / "oiol2.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def summarize_config(cfg: AppConfig) -> str:
    # A concise, human-readable summary for quick verification
    lines = [
        "=== Loaded Config Summary ===",
        f"[paths]",
        f"  labfile_root          : {cfg.paths.labfile_root}",
        f"[output]",
        f"  dir                   : {cfg.output.dir}",
        f"  file_stem_pattern     : {cfg.output.file_stem_pattern!r}",
        f"  point_format          : {cfg.output.point_format!r}",
        f"  header (len)          : {len(cfg.output.header)}",
        f"  footer (len)          : {len(cfg.output.footer)}",
        f"[xcel.pointfile_parms]",
        f"  point_spacing_mm      : {cfg.xcel_pointfile_parms.point_spacing_mm}",
        f"  meridians             : {cfg.xcel_pointfile_parms.meridians}",
        f"[xcel.options]",
        f"  use_vertex_code_from_lab : {cfg.xcel_options.use_vertex_code_from_lab}",
        f"  vertex_code              : {cfg.xcel_options.vertex_code}",
        "==============================",
    ]
    return "\n".join(lines)

def summarize_lens_design(ld: LensDesign, sample_keys: Optional[list[str]] = None) -> str:
    lines = [
        "=== Loaded Lens Design (simplified) ===",
        f"meta.design_name : {ld.meta.get('design_name')}",
        f"meta.partner     : {ld.meta.get('partner')}",
        f"meta.owner       : {ld.meta.get('owner')}",
        f"meta.material    : {ld.meta.get('material')}",
        f"param count      : {len(ld.params)}",
        "",
    ]
    # show a few important ones if present
    wanted = sample_keys or [
        "lens.diameter",
        "center.thickness",
        "optics.central_base_curve_radius",
        "optics.central_zone_diameter",
        "return_zone.width",
        "return_zone.depth",
        "landing_zone.angle",
        "landing_zone.width",
        "peripheral_edge_curve.depth",
        "peripheral_edge_curve.width",
        "edge.thickness",
        "power.vertex",
    ]
    for k in wanted:
        if k in ld.params:
            p = ld.params[k]
            lines.append(f"[{k}] default={p.default} min={p.min} max={p.max} step={p.step} ({p.units})")
    lines.append("=======================================")
    return "\n".join(lines)

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

# -----------------------
# CLI
# -----------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="oiol2",
        description="Optimum Infinite Orthokeratology Lens II - point-file builder (config loader stage)",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="Path to config.toml (defaults to <repo>/configs/config.toml)",
    )
    p.add_argument(
        "--design",
        type=Path,
        default=default_design_path(),
        help="Path to lens_design.toml (defaults to <repo>/data/lens_design.toml)",
    )
    p.add_argument(
        "--wo",
        type=str,
        required=True,
        help="Work order number (Lab File name is 'C' + WO under [paths.labfile_root])",
    )
    p.add_argument(
        "--lab-spec",
        type=Path,
        default=default_lab_spec_path(),
        help="Lab file mapping spec (defaults to <repo>/configs/lab_file.toml)",
    )
    p.add_argument(
        "--value-col-start",
        type=int,
        default=36,
        help="Starting column index for value field in fixed-width Lab File (default 36)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    setup_logging()

    logger = logging.getLogger("oiol2.main")

    config_path = args.config
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 2

    try:
        raw = load_toml(config_path)
        cfg = validate_and_build(raw)
        ensure_dirs(cfg)
    except Exception as e:
        logger.exception("Failed to load/validate config: %s", e)
        return 1

    summary = summarize_config(cfg)
    logger.info("\n%s", summary)

    # Load lens design (simple tables, no formulas/refs/validation)
    design_path = args.design if hasattr(args, "design") else default_design_path()
    if not design_path.exists():
        logger.error("Lens design file not found: %s", design_path)
        return 2

    try:
        lens_design = load_lens_design(design_path)
    except Exception as e:
        logger.exception("Failed to load lens design: %s", e)
        return 1

    logger.info("\n%s", summarize_lens_design(lens_design))   

    # ===== Load Lab File =====
    # Ensure we can import the local 'labfile' package
    ensure_labfile_importable()
    try:
        from labfile import load_lab_fields, parse_lab_file  # type: ignore
    except Exception as e:
        logger.exception("Cannot import 'labfile' module: %s", e)
        return 1

    # Resolve paths
    lab_dir: Path = cfg.paths.labfile_root
    lab_name = f"C{args.wo}"
    lab_path = lab_dir / lab_name

    if not lab_path.exists():
        logger.error("Lab File not found: %s", lab_path)
        return 2

    lab_spec_path: Path = args.lab_spec
    if not lab_spec_path.exists():
        logger.error("Lab field mapping spec not found: %s", lab_spec_path)
        return 2

    try:
        fields_spec = load_lab_fields(str(lab_spec_path))
        lab_data: dict[str, Any] = parse_lab_file(
            path=str(lab_path),
            fields_spec=fields_spec,
            VALUE_COL_START=int(args.value_col_start),
        )
    except Exception as e:
        logger.exception("Failed to parse Lab File: %s", e)
        return 1

    logger.info("\n%s", summarize_lab_result(lab_data))

    optic_zone_points = generate_optic_zone_meridional(lab_data)
    
    ########################
    # Plot the curves
    plot_meridional_curves(
        [Curve(label="Base Surface Optic Zone", points=optic_zone_points)],
        title="Optic/Treatment Zone (Base Surface)",
        xlim=(0, 8)
    )
    ########################

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
