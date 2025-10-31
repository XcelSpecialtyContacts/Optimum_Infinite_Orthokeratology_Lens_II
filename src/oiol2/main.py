# src/oiol2/main.py
from __future__ import annotations

import pathlib, sys
# Add <repo>/src to sys.path so 'oiol2' is importable when running from repo root
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional
#import re

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

# Load modules specific to this project
from oiol2.vis.plotting import plot_meridional_curves, Curve
from oiol2.geometry.meridional import (
    generate_optic_zone_meridional,
    generate_front_optic_zone_meridional,
    find_ct_fcr_jt_to_meet_jt_min, 
    _to_float,
    edge_normal_line_at_back_surface,
    generate_line_path,
    tangent_circle_below_with_points,
    generate_upper_semi_circle_path,
    calc_bs_edge_data
)
from oiol2.geometry_core import (
    conic_line_intersections,
    distance_between_points,
    slope_from_angle,
    y_intercept,
    slope_and_angle_of_line_tangent_to_curve,
    sigmoid_segment_with_end_slopes,
    point_along_line
)

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

#_number_re = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")

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

# def _to_float(v) -> float:
#     """
#     Coerce Lab File values to float.
#     Accepts:
#       - float/int
#       - strings like '8.70', '+0.75', '  10.5 mm', etc.
#       - dicts like {'value': '8.70'} or {'value': 8.70}
#     Raises ValueError if no numeric content is found.
#     """
#     if isinstance(v, (int, float)):
#         return float(v)
#     if isinstance(v, dict) and "value" in v:
#         return _to_float(v["value"])
#     s = str(v).strip()
#     m = _number_re.search(s)
#     if not m:
#         raise ValueError(f"Cannot parse numeric value from: {v!r}")
#     return float(m.group(0))

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

    ########################
    # Calculate the Base Curve optic zone radius bcoz_points
    bcoz_points = generate_optic_zone_meridional(lab_data)
    ########################

    ########################
    # Calculate the Front Curve optic zone radius, Center Thickness, and
    # Junction Thickness at the edge of optic zone
    R0_back   = _to_float(lab_data["BC"]) # BC optic zone radius
    K_back    = 0.0  # conic constant for back optic zone: sphere in this design
    x_edge    = _to_float(lab_data["BCOZDia"]) / 2.0 # half cord distance for optic zone
    power_D   = _to_float(lab_data["Power"]) # Sphere power for the lens
    index_ri  = _to_float(lab_data["RI"]) # Refractive Index of the material
    vertex_mm = _to_float(lab_data["Vertex"]) # How is lens power to be calculated (back vertex, or front vertex)
    ct_init   = _to_float(lab_data["CT"]) # This is intially the center thickness that was originally specified

    jt_min_mm = lens_design.params["center_zone.junction_thickness"].min
    ct_min_mm = lens_design.params["center_zone.thickness"].min
    ct_max_mm = lens_design.params["center_zone.thickness"].max

    # --- Validate initial center thickness ---
    if ct_init < ct_min_mm:
        logger.warning(
            "CT below minimum: %.3f mm < %.3f mm (adjusted to min limit).",
            ct_init, ct_min_mm
        )
        ct_init = ct_min_mm
    elif ct_init > ct_max_mm:
        logger.warning(
            "CT above maximum: %.3f mm > %.3f mm (adjusted to max limit).",
            ct_init, ct_max_mm
        )
        ct_init = ct_max_mm
    else:
        logger.debug(
            "CT within limits: %.3f mm (range %.3f–%.3f mm).",
            ct_init, ct_min_mm, ct_max_mm
        )

    result = find_ct_fcr_jt_to_meet_jt_min(
        power_D=power_D,
        R0_back=R0_back,
        K_back=K_back,
        index_ri=index_ri,
        ct_init_mm=ct_init,
        vertex_mm=vertex_mm,
        x_edge=x_edge,
        jt_min_mm=jt_min_mm,
        ct_min_mm=ct_min_mm,
        ct_max_mm=ct_max_mm,
        step_mm=0.001,
        max_iter=5000,
    )

    logger.info(
        "JT solve: converged=%s, iters=%d, CT=%.3f mm, FCR=%.3f mm, JT=%.3f mm%s",
        result.converged, result.iterations, result.ct, result.fcr, result.jt1,
        f" | note: {result.note}" if result.note else "",
    )

    CT  = result.ct
    FCR = result.fcr
    JT1 = result.jt1
    ########################

    ########################
    # Calculate front surface optic zone points
    bcoz_p_apex = (0, 0)
    bc_e_x, bc_e_y, jt1_m, jt1_b = edge_normal_line_at_back_surface(x_edge, R0_back, K_back) # computes the point at the end of the BC optic zone and the line normal the surface at that point
    bcoz_p_end = (bc_e_x, bc_e_y)
    fcoz_p_apex = (0, -CT)
    pts = conic_line_intersections(jt1_m, jt1_b, FCR, 0.0, -CT)
    fcoz_p_end = min(pts, key=lambda q: distance_between_points(bcoz_p_end, q))
    fcoz_points = generate_front_optic_zone_meridional(0.0, fcoz_p_end[0], CT, FCR)
    ########################

    ########################
    # Calculate JT1 points
    jt1_points = generate_line_path(bcoz_p_end[0], fcoz_p_end[0], jt1_m, jt1_b)
    ########################

    ########################
    # Calculate Base Surface Flat Axis Landing Zone path
    bslz_flat_p_start = (bcoz_p_end[0] + lens_design.params["return_zone.width"].default, bcoz_p_end[1] + _to_float(lab_data["RZDFlat"]))
    bslz_flat_m = slope_from_angle(_to_float(lab_data["LZAFlat"]))
    bslz_flat_b = y_intercept(bslz_flat_p_start[0], bslz_flat_p_start[1], bslz_flat_m)
    bslz_flat_ext_p_end = (_to_float(lab_data["Dia"]) / 2, bslz_flat_m * _to_float(lab_data["Dia"]) / 2 + bslz_flat_b)
    bslz_flat_ext_points = generate_line_path(bslz_flat_p_start[0], bslz_flat_ext_p_end[0], bslz_flat_m, bslz_flat_b)
    ########################

    ########################
    # Calculate Base Surface Steep Axis Landing Zone path
    bslz_steep_p_start = (bcoz_p_end[0] + lens_design.params["return_zone.width"].default, bcoz_p_end[1] + _to_float(lab_data["RZDSteep"]))
    bslz_steep_m = slope_from_angle(_to_float(lab_data["LZASteep"]))
    bslz_steep_b = y_intercept(bslz_steep_p_start[0], bslz_steep_p_start[1], bslz_steep_m)
    bslz_steep_ext_p_end = (_to_float(lab_data["Dia"]) / 2, bslz_steep_m * _to_float(lab_data["Dia"]) / 2 + bslz_steep_b)
    bslz_steep_ext_points = generate_line_path(bslz_steep_p_start[0], bslz_steep_ext_p_end[0], bslz_steep_m, bslz_steep_b)
    ########################
    
    ########################
    # Calculate Base Surface Flat Axis Return Zone
    bsrz_flat_p_start = bcoz_p_end
    bsrz_flat_p_end = bslz_flat_p_start
    bsrz_flat_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(_to_float(lab_data["BCOZDia"]) / 2.0, _to_float(lab_data["BC"]), 0.0)
    bsrz_flat_m_end = bslz_flat_m
    bsrz_flat_points = sigmoid_segment_with_end_slopes(bsrz_flat_p_start, bsrz_flat_p_end, bsrz_flat_m_start, bsrz_flat_m_end)
    ########################

    ########################
    # Calculate Base Surface Steep Axis Return Zone
    bsrz_steep_p_start = bcoz_p_end
    bsrz_steep_p_end = bslz_steep_p_start
    bsrz_steep_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(_to_float(lab_data["BCOZDia"]) / 2.0, _to_float(lab_data["BC"]), 0.0)
    bsrz_steep_m_end = bslz_steep_m
    bsrz_steep_points = sigmoid_segment_with_end_slopes(bsrz_steep_p_start, bsrz_steep_p_end, bsrz_steep_m_start, bsrz_steep_m_end)
    ########################

    ########################
    # Calculate the base surface Peripheral Edge Curve for the flat axis.
    bsez_flat_ext_p_start = (
        _to_float(lab_data["Dia"]) / 2 - lens_design.params["peripheral_edge_curve.width"].default,
        bslz_flat_m * (_to_float(lab_data["Dia"]) / 2 - lens_design.params["peripheral_edge_curve.width"].default) + bslz_flat_b
    )
    bsez_flat_ext_p_end = (
        bslz_flat_ext_p_end[0],
        bsez_flat_ext_p_start[1] + _to_float(lab_data["PECDFlat"])
    )
    bsez_flat_m = _to_float(lab_data["PECDFlat"]) / lens_design.params["peripheral_edge_curve.width"].default
    bsez_flat_b = bsez_flat_ext_p_end[1] - bsez_flat_m * bsez_flat_ext_p_end[0]
    bsez_flat_ext_points = generate_line_path(bsez_flat_ext_p_start[0], bsez_flat_ext_p_end[0], bsez_flat_m, bsez_flat_b)
    ########################

    ########################
    # Calculate the base surface Peripheral Edge Curve for the steep axis.
    bsez_steep_ext_p_start = (
        _to_float(lab_data["Dia"]) / 2 - lens_design.params["peripheral_edge_curve.width"].default,
        bslz_steep_m * (_to_float(lab_data["Dia"]) / 2 - lens_design.params["peripheral_edge_curve.width"].default) + bslz_steep_b
    )
    bsez_steep_ext_p_end = (
        bslz_steep_ext_p_end[0],
        bsez_steep_ext_p_start[1] + _to_float(lab_data["PECDSteep"])
    )
    bsez_steep_m = _to_float(lab_data["PECDSteep"]) / lens_design.params["peripheral_edge_curve.width"].default
    bsez_steep_b = bsez_steep_ext_p_end[1] - bsez_steep_m * bsez_steep_ext_p_end[0]
    bsez_steep_ext_points = generate_line_path(bsez_steep_ext_p_start[0], bsez_steep_ext_p_end[0], bsez_steep_m, bsez_steep_b)
    ########################

    ########################
    # On the base surface calculate the blend zone between landing zone and the edge zone for the flat axis.
    bs_lz_to_ez_blend_flat_ctr_p, bs_lz_to_ez_blend_flat_tangent_p_1, bs_lz_to_ez_blend_flat_tangent_p_2 = tangent_circle_below_with_points(
        bslz_flat_m,
        bslz_flat_b,
        bsez_flat_m,
        bsez_flat_b,
        lens_design.params["blend_curve_landing_edge.radius"].default
    )
    bs_lz_to_ez_blend_flat_points = generate_upper_semi_circle_path(
        lens_design.params["blend_curve_landing_edge.radius"].default,
        bs_lz_to_ez_blend_flat_ctr_p,
        bs_lz_to_ez_blend_flat_tangent_p_1[0],
        bs_lz_to_ez_blend_flat_tangent_p_2[0],
        201
    )
    ########################

    ########################
    # On the base surface calculate the blend zone between landing zone and the edge zone for the steep axis.
    bs_lz_to_ez_blend_steep_ctr_p, bs_lz_to_ez_blend_steep_tangent_p_1, bs_lz_to_ez_blend_steep_tangent_p_2 = tangent_circle_below_with_points(
        bslz_steep_m,
        bslz_steep_b,
        bsez_steep_m,
        bsez_steep_b,
        lens_design.params["blend_curve_landing_edge.radius"].default
    )
    bs_lz_to_ez_blend_steep_points = generate_upper_semi_circle_path(
        lens_design.params["blend_curve_landing_edge.radius"].default,
        bs_lz_to_ez_blend_steep_ctr_p,
        bs_lz_to_ez_blend_steep_tangent_p_1[0],
        bs_lz_to_ez_blend_steep_tangent_p_2[0],
        201
    )
    ########################

    ########################
    # On the base surface calculate the edge radius path for the flat axis.
    bs_edge_radius_flat_center_p, bs_edge_radius_flat_tangent_el_p, bs_edge_radius_flat_tangent_vert_p = calc_bs_edge_data(
        _to_float(lab_data["Dia"]) / 2,
        bsez_flat_m,
        bsez_flat_b,
        _to_float(lab_data["ET"]) / 2
    )
    bs_edge_radius_flat_points = generate_upper_semi_circle_path(
        _to_float(lab_data["ET"]) / 2,
        bs_edge_radius_flat_center_p,
        bs_edge_radius_flat_tangent_el_p[0],
        bs_edge_radius_flat_tangent_vert_p[0],
        201
    )
    ########################

    ########################
    # On the base surface calculate the edge radius path for the steep axis. bs_edge_radius_steep_points
    bs_edge_radius_steep_center_p, bs_edge_radius_steep_tangent_el_p, bs_edge_radius_steep_tangent_vert_p = calc_bs_edge_data(
        _to_float(lab_data["Dia"]) / 2,
        bsez_steep_m,
        bsez_steep_b,
        _to_float(lab_data["ET"]) / 2
    )
    bs_edge_radius_steep_points = generate_upper_semi_circle_path(
        _to_float(lab_data["ET"]) / 2,
        bs_edge_radius_steep_center_p,
        bs_edge_radius_steep_tangent_el_p[0],
        bs_edge_radius_steep_tangent_vert_p[0],
        201
    )
    ########################

    ########################
    # Compute Junction Thickness at Landing Zone and Edge Zone for the flat axis
    JT2 = _to_float(lab_data["ET"]) + 0.03
    jt2_flat_m = -1 / bslz_flat_m
    jt2_flat_b = bsez_flat_ext_p_start[1] - jt2_flat_m * bsez_flat_ext_p_start[0]
    jt2_flat_p_end = point_along_line(jt2_flat_m, jt2_flat_b, JT2, 1, bsez_flat_ext_p_start[0])
    jt2_flat_points = generate_line_path(bsez_flat_ext_p_start[0], jt2_flat_p_end[0], jt2_flat_m, jt2_flat_b)
    print(f"JT2 Flat start: {bsez_flat_ext_p_start}")
    print(f"JT2 Flat end: {jt2_flat_p_end}")
    ########################

    ########################
    # Plot the curves
    plot_meridional_curves(
        [
            Curve(label="Base Surface Optic Zone", points=bcoz_points),
            Curve(label="Front Surface Optic Zone", points=fcoz_points),
            Curve(points=jt1_points),
            Curve(points=bsrz_flat_points),
            Curve(points=bslz_flat_ext_points),
            Curve(points=bsez_flat_ext_points),
            Curve(points=bs_lz_to_ez_blend_flat_points),
            Curve(points=bs_edge_radius_flat_points),
            Curve(label="JT2 Flat", points=jt2_flat_points)
        ],
        title="Optimum Infinite Orthokeratology Lens II",
        xlim=(0, 8)
    )
    ########################

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
