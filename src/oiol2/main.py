# src/oiol2/main.py
from __future__ import annotations

#*
from pathlib import Path # Needed for handling OS paths, makes it cleaner
import sys # Access to system-specific parameters and functions
# Add <repo>/src to sys.path so 'oiol2' is importable when running from repo root
#ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import argparse # for command line argument parsing
import logging #* for logging and debugging
import time #* needed for cleaning up log file
from datetime import datetime, timedelta #* needed for cleaning up log file
from dataclasses import dataclass # Needed for storing data in memory
from typing import Any, Mapping, Optional # Needed for handling data types

#*
# For parsing TOML files
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

# Load modules specific to this project
from oiol2.vis.plotting import plot_meridional_curves, Curve
from oiol2.dac_pointfile_writer import write_base_surface_point_file, write_front_surface_point_file
from oiol2.geometry.meridional import (
    generate_optic_zone_meridional,
    generate_front_optic_zone_meridional,
    find_ct_fcr_jt_to_meet_jt_min, 
    _to_float,
    edge_normal_line_at_back_surface,
    generate_line_path,
    tangent_circle_below_with_points,
    generate_upper_semi_circle_path,
    generate_lower_semi_circle_path,
    calc_bs_edge_data,
    tangent_line_from_external_point,
    trim_curve_by_x,
    concat_point_lists,
    reverse_points,
    curve_length,
    resample_curve_by_arclength
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

from oiol2.helper import (
    repo_root_from_this_file,
    default_config_path,
    default_lab_spec_path,
    ensure_labfile_importable,
    default_logs_dir,
    ensure_dirs,
    default_design_path,
    load_toml_file,
    load_toml,
    _expand_pathlike,
    _coerce_float,
    summarize_lab_result
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
# Helpers not in helpers.py
# -----------------------
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

def cleanup_old_logs(max_age_hours: float = 24.0) -> None:
    #
    # Delete log files in the logs directory that are older than max_age_hours.
    #
    logs_dir = default_logs_dir()
    if not logs_dir.exists():
        return

    cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

    deleted_count = 0
    for log_file in logs_dir.glob("oiol2-*.log"):
        if log_file.is_file():
            try:
                # Using modification time is usually good enough
                mtime = log_file.stat().st_mtime
                if mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
                    print(f"Deleted old log: {log_file.name}")
            except Exception as e:
                print(f"Failed to delete {log_file.name}: {e}")

    if deleted_count > 0:
        print(f"Cleanup: removed {deleted_count} old log file(s)")
    else:
        existing = list(logs_dir.glob("oiol2-*.log"))
        if existing:
            print(f"No logs older than {max_age_hours}h found ({len(existing)} current log files)")
        else:
            print("No existing log files found")


def setup_logging() -> logging.Logger:
    #
    # Creates a new timestamped log file for each run.
    # Returns the configured logger.
    #
    logs_dir = default_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create new log file with timestamp for each run
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_filename = f"oiol2-{timestamp}.log"
    log_path = logs_dir / log_filename

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True  # reset any previous configuration
    )

    logger = logging.getLogger("oiol2")
    logger.info(f"Logging started - log file: {log_path.name}")
    return logger

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
    p.add_argument(
        "--plot",
        action="store_true",
        help="If set, generate and show meridional plots and write visualization point files"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cleanup_old_logs(max_age_hours=24.0)
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
    bcoz_points = generate_optic_zone_meridional(lab_data, int((_to_float(lab_data["BCOZDia"]) / 2.0) / 0.0005))

    logger.info("\nBCOZ apex point: %s \nBCOZ end point: %s", str(bcoz_points[0]), str(bcoz_points[-1]))
    ########################

    ########################
    # Calculate the Front Curve optic zone radius, Center Thickness, and
    # Junction Thickness at the edge of optic zone
    if lab_data['BC_actual']['value'] != "":
        R0_back = _to_float(lab_data["BC_actual"]) # BC radius that was actually produced
    else:
        R0_back = _to_float(lab_data["BC"]) # BC optic zone radius
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

    CT  = result.ct
    FCR = result.fcr
    JT1 = result.jt1

    logger.info("\nCT = %.3f, FCR = %.3f, JT1 = %.3f", CT, FCR, JT1)
    ########################

    ########################
    # Calculate front surface optic zone points
    bcoz_p_apex = (0, 0)
    bc_e_x, bc_e_y, jt1_m, jt1_b = edge_normal_line_at_back_surface(x_edge, R0_back, K_back) # computes the point at the end of the BC optic zone and the line normal the surface at that point
    bcoz_p_end = (bc_e_x, bc_e_y)
    fcoz_p_apex = (0, -CT)
    pts = conic_line_intersections(jt1_m, jt1_b, FCR, 0.0, -CT)
    fcoz_p_end = min(pts, key=lambda q: distance_between_points(bcoz_p_end, q))
    fcoz_points = generate_front_optic_zone_meridional(0.0, fcoz_p_end[0], CT, FCR, False, int(fcoz_p_end[0] / 0.0005))

    logger.info("\nFCOZ apex: %s \nFCOZ End: %s", fcoz_points[0], fcoz_points[-1])
    ########################

    ########################
    # Calculate JT1 points
    jt1_points = generate_line_path(bcoz_p_end[0], fcoz_p_end[0], jt1_m, jt1_b, int(JT1 / 0.0005))

    logger.info("\nJT1 Base Surface point: %s \
                 \nJT1 Front Surface point: %s", \
                 jt1_points[0], jt1_points[-1])
    ########################

    ########################
    # Calculate Landing Zone Width
    LZW = _to_float(lab_data["Dia"]) / 2 - _to_float(lab_data["BCOZDia"]) / 2 - lens_design.params["return_zone.width"].default - lens_design.params["peripheral_edge_curve.width"].default
    
    logger.info("\nLZW = %.3f", LZW)
    ########################

    ########################
    # Calculate Base Surface Flat Axis Landing Zone path
    bslz_flat_p_start = (bcoz_p_end[0] + lens_design.params["return_zone.width"].default, bcoz_p_end[1] + _to_float(lab_data["RZDFlat"]))
    bslz_flat_m = slope_from_angle(_to_float(lab_data["LZAFlat"]))
    bslz_flat_b = y_intercept(bslz_flat_p_start[0], bslz_flat_p_start[1], bslz_flat_m)
    bslz_flat_ext_p_end = (_to_float(lab_data["Dia"]) / 2, bslz_flat_m * _to_float(lab_data["Dia"]) / 2 + bslz_flat_b)
    bslz_flat_ext_points = generate_line_path(
        bslz_flat_p_start[0],
        bslz_flat_ext_p_end[0],
        bslz_flat_m,
        bslz_flat_b,
        int(LZW / 0.0005)
    )
    logger.info("\nLanding Zone angle, flat: %.3f \
                 \nBase Surface Landing Zone start point, flat axis: %s \
                 \nBase Surface Landing Zone (extended path) end point, flat axis: %s", \
                 _to_float(lab_data["LZAFlat"]), bslz_flat_ext_points[0], bslz_flat_ext_points[-1])
    ########################

    ########################
    # Calculate Base Surface Steep Axis Landing Zone path
    bslz_steep_p_start = (bcoz_p_end[0] + lens_design.params["return_zone.width"].default, bcoz_p_end[1] + _to_float(lab_data["RZDSteep"]))
    bslz_steep_m = slope_from_angle(_to_float(lab_data["LZASteep"]))
    bslz_steep_b = y_intercept(bslz_steep_p_start[0], bslz_steep_p_start[1], bslz_steep_m)
    bslz_steep_ext_p_end = (_to_float(lab_data["Dia"]) / 2, bslz_steep_m * _to_float(lab_data["Dia"]) / 2 + bslz_steep_b)
    bslz_steep_ext_points = generate_line_path(
        bslz_steep_p_start[0],
        bslz_steep_ext_p_end[0],
        bslz_steep_m,
        bslz_steep_b,
        int(LZW / 0.0005)
    )
    logger.info("\nLanding Zone angle, steep: %.3f \
                 \nBase Surface Landing Zone start point, steep axis: %s \
                 \nBase Surface Landing Zone (extended path) end point, steep axis: %s", \
                 _to_float(lab_data["LZASteep"]), bslz_steep_ext_points[0], bslz_steep_ext_points[-1])
    ########################
    
    ########################
    # Calculate Base Surface Flat Axis Return Zone
    bsrz_flat_p_start = bcoz_p_end
    bsrz_flat_p_end = bslz_flat_p_start
    bsrz_flat_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(_to_float(lab_data["BCOZDia"]) / 2.0, _to_float(lab_data["BC"]), 0.0)
    bsrz_flat_m_end = bslz_flat_m
    bsrz_flat_points = sigmoid_segment_with_end_slopes(
        bsrz_flat_p_start,
        bsrz_flat_p_end,
        bsrz_flat_m_start,
        bsrz_flat_m_end,
        int(lens_design.params["return_zone.width"].default / 0.0005)
    )
    logger.info("\nReturn Zone Width: %.3f \
                 \nReturn Zone Depth, flat: %.3f \
                 \nReturn Zone start point, flat axis: %s \
                 \nReturn Zone end point, flat axis: %s", \
                 lens_design.params["return_zone.width"].default, _to_float(lab_data["RZDFlat"]), bsrz_flat_points[0], bsrz_flat_points[-1])
    ########################

    ########################
    # Calculate Base Surface Steep Axis Return Zone
    bsrz_steep_p_start = bcoz_p_end
    bsrz_steep_p_end = bslz_steep_p_start
    bsrz_steep_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(_to_float(lab_data["BCOZDia"]) / 2.0, _to_float(lab_data["BC"]), 0.0)
    bsrz_steep_m_end = bslz_steep_m
    bsrz_steep_points = sigmoid_segment_with_end_slopes(
        bsrz_steep_p_start,
        bsrz_steep_p_end,
        bsrz_steep_m_start,
        bsrz_steep_m_end,
        int(lens_design.params["return_zone.width"].default / 0.0005)
    )
    logger.info("\nReturn Zone Width: %.3f \
                 \nReturn Zone Depth, steep: %.3f \
                 \nReturn Zone start point, steep axis: %s \
                 \nReturn Zone end point, steep axis: %s", \
                 lens_design.params["return_zone.width"].default, _to_float(lab_data["RZDSteep"]), bsrz_steep_points[0], bsrz_steep_points[-1])
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
    bsez_flat_ext_points = generate_line_path(
        bsez_flat_ext_p_start[0],
        bsez_flat_ext_p_end[0],
        bsez_flat_m,
        bsez_flat_b,
        int(lens_design.params["peripheral_edge_curve.width"].default / 0.0005)
    )
    logger.info("\nBase Surface Edge Curve width, flat axis: %.3f \
                 \nBase Surface Edge Curve depth, flat axis: %.3f \
                 \nBase Surface Edge Curve (extended path) start point, flat axis: %s \
                 \nBase Surface Edge Curve (extended path) end point, flat axis: %s", \
                 lens_design.params["peripheral_edge_curve.width"].default, _to_float(lab_data["PECDFlat"]), bsez_flat_ext_points[0], bsez_flat_ext_points[-1])
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
    bsez_steep_ext_points = generate_line_path(
        bsez_steep_ext_p_start[0],
        bsez_steep_ext_p_end[0],
        bsez_steep_m,
        bsez_steep_b,
        int(lens_design.params["peripheral_edge_curve.width"].default / 0.0005)
    )
    logger.info("\nBase Surface Edge Curve width, flat axis: %.3f \
                 \nBase Surface Edge Curve depth, flat axis: %.3f \
                 \nBase Surface Edge Curve (extended path) start point, steep axis: %s \
                 \nBase Surface Edge Curve (extended path) end point, steep axis: %s", \
                 lens_design.params["peripheral_edge_curve.width"].default, _to_float(lab_data["PECDSteep"]), bsez_steep_ext_points[0], bsez_steep_ext_points[-1])
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
        int((bs_lz_to_ez_blend_flat_tangent_p_2[0] - bs_lz_to_ez_blend_flat_tangent_p_1[0]) / 0.0005)
    )
    logger.info("\nBlend Zone between Landing Zone and Edge Zone start point, flat axis: %s \
                 \nBlend Zone between Landing Zone and Edge Zone end point, flat axis: %s", \
                 bs_lz_to_ez_blend_flat_points[0], bs_lz_to_ez_blend_flat_points[-1])
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
        int((bs_lz_to_ez_blend_steep_tangent_p_2[0] - bs_lz_to_ez_blend_steep_tangent_p_1[0]) / 0.0005)
    )
    logger.info("\nBlend Zone between Landing Zone and Edge Zone start point, steep axis: %s \
                 \nBlend Zone between Landing Zone and Edge Zone end point, steep axis: %s", \
                 bs_lz_to_ez_blend_steep_points[0], bs_lz_to_ez_blend_steep_points[-1])
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
        int((bs_edge_radius_flat_tangent_vert_p[0] - bs_edge_radius_flat_tangent_el_p[0]) / 0.0005)
    )
    logger.info("\nEdge Radius: %.3f \
                 \nBase Surface Edge Radius start point, flat axis: %s \
                 \nBase Surface Edge Radius end point, flat axis: %s", \
                 _to_float(lab_data["ET"]) / 2, bs_edge_radius_flat_points[0], bs_edge_radius_flat_points[-1])
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
        int((bs_edge_radius_steep_tangent_vert_p[0] - bs_edge_radius_steep_tangent_el_p[0]) / 0.0005)
    )
    logger.info("\nEdge Radius: %.3f \
                 \nBase Surface Edge Radius start point, steep axis: %s \
                 \nBase Surface Edge Radius end point, steep axis: %s", \
                 _to_float(lab_data["ET"]) / 2, bs_edge_radius_steep_points[0], bs_edge_radius_steep_points[-1])
    ########################

    ########################
    # Compute Junction Thickness at Landing Zone and Edge Zone
    JT2 = _to_float(lab_data["ET"]) + 0.03
    logger.info("\nJT2 = %.3f", JT2)
    ########################

    ########################
    # Compute Junction Thickness path at Landing Zone and Edge Zone for the flat axis
    jt2_flat_m = -1 / bslz_flat_m
    jt2_flat_b = bsez_flat_ext_p_start[1] - jt2_flat_m * bsez_flat_ext_p_start[0]
    jt2_flat_p_end = point_along_line(jt2_flat_m, jt2_flat_b, JT2, 1, bsez_flat_ext_p_start[0])
    jt2_flat_points = generate_line_path(
        bsez_flat_ext_p_start[0],
        jt2_flat_p_end[0],
        jt2_flat_m,
        jt2_flat_b,
        int(JT2 / 0.0005)
    )
    logger.info("\nJT1 point on Base Surface, flat axis: %s \
                 \nJT1 point on Front Surface, flat axis: %s", \
                 jt2_flat_points[0], jt2_flat_points[-1])
    ########################

    ########################
    # Compute Junction Thickness path at Landing Zone and Edge Zone for the steep axis
    jt2_steep_m = -1 / bslz_steep_m
    jt2_steep_b = bsez_steep_ext_p_start[1] - jt2_steep_m * bsez_steep_ext_p_start[0]
    jt2_steep_p_end = point_along_line(jt2_steep_m, jt2_steep_b, JT2, 1, bsez_steep_ext_p_start[0])
    jt2_steep_points = generate_line_path(
        bsez_steep_ext_p_start[0], 
        jt2_steep_p_end[0],
        jt2_steep_m, 
        jt2_steep_b,
        int(JT2 / 0.0005)
    )
    logger.info("\nJT1 point on Base Surface, steep axis: %s \
                 \nJT1 point on Front Surface, steep axis: %s", \
                 jt2_steep_points[0], jt2_steep_points[-1])
    ########################

    ########################
    # Calculate the front surface Peripheral Edge Curve for the flat axis.
    fsez_flat_p_start = jt2_flat_p_end
    fsez_flat_m, fsez_flat_b, fsez_flat_p_end = tangent_line_from_external_point(
        bs_edge_radius_flat_center_p,
        _to_float(lab_data["ET"]) / 2,
        fsez_flat_p_start
    )
    fsez_flat_points = generate_line_path(
        fsez_flat_p_start[0],
        fsez_flat_p_end[0],
        fsez_flat_m,
        fsez_flat_b,
        int((fsez_flat_p_end[0] - fsez_flat_p_start[0]) / 0.0005)
    )
    logger.info("\nFront Surface Peripheral Edge Zone start point, flat axis: %s \
                 \nFront Surface Peripheral Edge Zone end point, flat axis: %s", \
                 fsez_flat_points[0], fsez_flat_points[-1])
    ########################

    ########################
    # Calculate the front surface Peripheral Edge Curve for the steep axis.
    fsez_steep_p_start = jt2_steep_p_end
    fsez_steep_m, fsez_steep_b, fsez_steep_p_end = tangent_line_from_external_point(
        bs_edge_radius_steep_center_p,
        _to_float(lab_data["ET"]) / 2,
        fsez_steep_p_start
    )
    fsez_steep_points = generate_line_path(
        fsez_steep_p_start[0],
        fsez_steep_p_end[0],
        fsez_steep_m,
        fsez_steep_b,
        int((fsez_steep_p_end[0] - fsez_steep_p_start[0]) / 0.0005)
    )
    logger.info("\nFront Surface Peripheral Edge Zone start point, steep axis: %s \
                 \nFront Surface Peripheral Edge zone end point, steep axis: %s", \
                 fsez_steep_points[0], fsez_steep_points[-1])
    ########################

    ########################
    # On the front surface calculate the edge radius path for the flat axis.
    fs_edge_radius_flat_points = generate_lower_semi_circle_path(
        _to_float(lab_data["ET"]) / 2,
        bs_edge_radius_flat_center_p,
        fsez_flat_p_end[0],
        bs_edge_radius_flat_tangent_vert_p[0],
        int((bs_edge_radius_flat_tangent_vert_p[0] - fsez_flat_p_end[0]) / 0.0005)
    )
    logger.info("\nEdge Radius: %.3f \
                 \nFront Surface Edge Radius start point, flat axis: %s \
                 \nFront Surface Edge Radius end point, flat axis: %s", \
                 _to_float(lab_data["ET"]) / 2, fs_edge_radius_flat_points[0], fs_edge_radius_flat_points[-1])
    ########################

    ########################
    # On the front surface calculate the edge radius path for the steep axis.
    fs_edge_radius_steep_points = generate_lower_semi_circle_path(
        _to_float(lab_data["ET"]) / 2,
        bs_edge_radius_steep_center_p,
        fsez_steep_p_end[0],
        bs_edge_radius_steep_tangent_vert_p[0],
        int((bs_edge_radius_steep_tangent_vert_p[0] - fsez_steep_p_end[0]) / 0.0005)
    )
    logger.info("\nEdge Radius: %.3f \
                 \nFront Surface Edge Radius start point, steep axis: %s \
                 \nFront Surface Edge Radius end point, steep axis: %s", \
                 _to_float(lab_data["ET"]) / 2, fs_edge_radius_steep_points[0], fs_edge_radius_steep_points[-1])
    ########################

    ########################
    # On the front surface calculate the peripheral curve path for the flat axis.
    fspc1_flat_p_start = fcoz_p_end
    fspc1_flat_p_end = fsez_flat_p_start
    fspc1_flat_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(fcoz_p_end[0], FCR, 0.0)
    fspc1_flat_m_end = fsez_flat_m
    fspc1_flat_points = sigmoid_segment_with_end_slopes(
        fspc1_flat_p_start,
        fspc1_flat_p_end,
        fspc1_flat_m_start,
        fspc1_flat_m_end,
        int((fspc1_flat_p_end[0] - fspc1_flat_p_start[0]) / 0.0005)
    )
    logger.info("\nFront Surface Peripheral Curve between Optic Zone and Edge Zone start point, flat axis: %s \
                 \nFront Surface Peripheral Curve between Optic Zone and Edge Zone end point, flat axis: %s", \
                 fspc1_flat_points[0], fspc1_flat_points[-1])
    ########################

    ########################
    # On the front surface calculate the peripheral curve path for the steep axis.
    fspc1_steep_p_start = fcoz_p_end
    fspc1_steep_p_end = fsez_steep_p_start
    fspc1_steep_m_start, _, _ = slope_and_angle_of_line_tangent_to_curve(fcoz_p_end[0], FCR, 0.0)
    fspc1_steep_m_end = fsez_steep_m
    fspc1_steep_points = sigmoid_segment_with_end_slopes(
        fspc1_steep_p_start,
        fspc1_steep_p_end,
        fspc1_steep_m_start,
        fspc1_steep_m_end,
        int((fspc1_steep_p_end[0] - fspc1_steep_p_start[0]) / 0.0005)
    )
    logger.info("\nFront Surface Peripheral Curve between Optic Zone and Edge Zone start point, steep axis: %s \
                 \nFront Surface Peripheral Curve between Optic Zone and Edge Zone end point, steep axis: %s", \
                 fspc1_steep_points[0], fspc1_steep_points[-1])
    ########################

    ########################
    # Compute the Base Surface Flat Meridian
    bs_meridian_flat_points = concat_point_lists(bcoz_points, bsrz_flat_points) # concatenate BC Optic Zone with BS Reverse Zone
    temp_points = trim_curve_by_x(bslz_flat_ext_points, x_end = bs_lz_to_ez_blend_flat_tangent_p_1[0])
    bs_meridian_flat_points = concat_point_lists(bs_meridian_flat_points, temp_points) # concatenate BS Meridian with BS Landing Zone
    bs_meridian_flat_points = concat_point_lists(bs_meridian_flat_points, bs_lz_to_ez_blend_flat_points) # concatenate BS Meridian with BS Landing Zone to Edge Zone Blend
    temp_points = trim_curve_by_x(bsez_flat_ext_points, x_start = bs_lz_to_ez_blend_flat_tangent_p_2[0], x_end = bs_edge_radius_flat_tangent_el_p[0])
    bs_meridian_flat_points = concat_point_lists(bs_meridian_flat_points, temp_points) # concatenate BS Meridian with BS Edge Zone
    bs_meridian_flat_points = concat_point_lists(bs_meridian_flat_points, bs_edge_radius_flat_points) # concatenate BS Meridian with BS Edge Radius BS Side
    temp_points = reverse_points(fs_edge_radius_flat_points)
    bs_meridian_flat_points = concat_point_lists(bs_meridian_flat_points, temp_points) # concatenate BS Meridian with BS Edge Radius FS Side
    logger.info("\nBase Surface flat meridional line start point: %s \
                 \nBase Surface flat meridional line end point: %s", \
                 bs_meridian_flat_points[0], bs_meridian_flat_points[-1])
    ########################

    ########################
    # Compute the Base Surface Steep Meridian bs_meridian_steep_points
    bs_meridian_steep_points = concat_point_lists(bcoz_points, bsrz_steep_points) # concatenate BC Optic Zone with BS Reverse Zone
    temp_points = trim_curve_by_x(bslz_steep_ext_points, x_end = bs_lz_to_ez_blend_steep_tangent_p_1[0])
    bs_meridian_steep_points = concat_point_lists(bs_meridian_steep_points, temp_points) # concatenate BS Meridian with BS Landing Zone
    bs_meridian_steep_points = concat_point_lists(bs_meridian_steep_points, bs_lz_to_ez_blend_steep_points) # concatenate BS Meridian with BS Landing Zone to Edge Zone Blend
    temp_points = trim_curve_by_x(bsez_steep_ext_points, x_start = bs_lz_to_ez_blend_steep_tangent_p_2[0], x_end = bs_edge_radius_steep_tangent_el_p[0])
    bs_meridian_steep_points = concat_point_lists(bs_meridian_steep_points, temp_points) # concatenate BS Meridian with BS Edge Zone
    bs_meridian_steep_points = concat_point_lists(bs_meridian_steep_points, bs_edge_radius_steep_points) # concatenate BS Meridian with BS Edge Radius BS Side
    temp_points = reverse_points(fs_edge_radius_steep_points)
    bs_meridian_steep_points = concat_point_lists(bs_meridian_steep_points, temp_points) # concatenate BS Meridian with BS Edge Radius FS Side
    logger.info("\nBase Surface steep meridional line start point: %s \
                 \nBase Surface steep meridional line end point: %s", \
                 bs_meridian_steep_points[0], bs_meridian_steep_points[-1])
    ########################

    ########################
    # Compute the Front Surface Flat Meridian
    fs_meridian_flat_points = concat_point_lists(fcoz_points, fspc1_flat_points) # concatenate FC Optic Zone with FS PC1
    fs_meridian_flat_points = concat_point_lists(fs_meridian_flat_points, fsez_flat_points) # concatenate FS Meridian with FS Edge Zone
    logger.info("\nFront Surface flat meridional line start point: %s \
                 \nFront Surface flat meridional line end point: %s", \
                 fs_meridian_flat_points[0], fs_meridian_flat_points[-1])
    ########################

    ########################
    # Compute the Front Surface Steep Meridian
    fs_meridian_steep_points = concat_point_lists(fcoz_points, fspc1_steep_points) # concatenate FC Optic Zone with FS PC1
    fs_meridian_steep_points = concat_point_lists(fs_meridian_steep_points, fsez_steep_points) # concatenate FS Meridian with FS Edge Zone
    logger.info("\nFront Surface steep meridional line start point: %s \
                 \nFront Surface steep meridional line end point: %s", \
                 fs_meridian_steep_points[0], fs_meridian_steep_points[-1])
    ########################

    ########################
    # Number of points the meridians will contain
    bs_meridian_flat_curve_length = curve_length(bs_meridian_flat_points)
    fs_meridian_flat_curve_length = curve_length(fs_meridian_flat_points)
    bs_meridian_steep_curve_length = curve_length(bs_meridian_steep_points)
    fs_meridian_steep_curve_length = curve_length(fs_meridian_steep_points)
    bs_meridian_point_count = int(max([bs_meridian_flat_curve_length, bs_meridian_steep_curve_length]) / 0.005)
    fs_meridian_point_count = int(max([fs_meridian_flat_curve_length, fs_meridian_steep_curve_length]) / 0.005)
    logger.info("\nBase Surface meridian point count: %s \
                 \nFront Surface meridian point count: %s", \
                 bs_meridian_point_count, fs_meridian_point_count)
    ########################

    ########################
    # Resample meridian curves so that all the base surface meridians contain the same number of points.
    # Resample meridian curves so that all the front surface meridians contain the same number of points.
    bs_meridian_flat_points_rs = resample_curve_by_arclength(bs_meridian_flat_points, bs_meridian_point_count)
    bs_meridian_steep_points_rs = resample_curve_by_arclength(bs_meridian_steep_points, bs_meridian_point_count)
    fs_meridian_flat_points_rs = resample_curve_by_arclength(fs_meridian_flat_points, fs_meridian_point_count)
    fs_meridian_steep_points_rs = resample_curve_by_arclength(fs_meridian_steep_points, fs_meridian_point_count)
    logger.info("\nBase Surface flat meridional line recalculated with computed point count start point: %s \
                 \nBase Surface flat meridional line recalculated with computed point count end point: %s \
                 \nBase Surface steep meridional line recalculated with computed point count start point: %s \
                 \nBase Surface steep meridional line recalculated with computed point count end point: %s \
                 \nFront Surface flat meridional line recalculated with computed point count start point: %s \
                 \nFront Surface flat meridional line recalculated with computed point count end point: %s \
                 \nFront Surface steep meridional line recalculated with computed point count start point: %s \
                 \nFront Surface steep meridional line recalculated with computed point count end point: %s", \
                 bs_meridian_flat_points_rs[0], bs_meridian_flat_points_rs[-1], \
                 bs_meridian_steep_points_rs[0], bs_meridian_steep_points_rs[-1], \
                 fs_meridian_flat_points_rs[0], fs_meridian_flat_points_rs[-1], \
                 fs_meridian_steep_points_rs[0], fs_meridian_steep_points_rs[-1])
    ########################

    ########################
    # Create a dictionary with the point file header data.
    header_data = {
        "non_symmetric_base": {
            "value": 0,
            "comment": "rotationally symmetrical base surface"
        },
        "non_symmetric_front": {
            "value": 0,
            "comment": "rotationally symmetrical front surface"
        },
        "no_of_base_surfaces": {
            "value": 1,
            "comment": "number of continuous surfaces that make up the lens base surface"
        },
        "no_of_front_surfaces": {
            "value": 1,
            "comment": "number of continuous surfaces that make up the lens front surface"
        },
        "BC_horizontal": {
            "value": _to_float(lab_data["BC"]),
            "comment": "the base curve radius in the horizontal meridian (information only)"
        },
        "FC_horizontal": {
            "value": FCR,
            "comment": "the front curve radius in the horizontal meridian (information only)"
        },
        "BC_vertical": {
            "value": _to_float(lab_data["BC"]),
            "comment": "the base curve radius in the vertical meridian (information only)"
        },
        "FC_vertical": {
            "value": FCR,
            "comment": "the front curve radius in the vertical meridian (information only)"
        },
        "BCOZ_dia": {
            "value": _to_float(lab_data["BCOZDia"]),
            "comment": "the base curve optic zone diameter (information only)"
        },
        "FCOZ_dia": {
            "value": fcoz_p_end[0] * 2,
            "comment": "the front curve optic zone diameter (information only)"
        },
        "lens_dia": {
            "value": _to_float(lab_data["Dia"]),
            "comment": "lens diameter"
        },
        "no_of_parts_to_cut": {
            "value": 0,
            "comment": "number of parts to cut"
        },
        "ct": {
            "value": CT,
            "comment": "center thickness"
        },
        "lens_sag_bs": {
            "value": round((bsez_flat_ext_p_end[1] + bsez_steep_ext_p_end[1]) / 2, 3),
            "comment": "average base surface sag without edge radius (information only)"
        },
        "no_of_diag_marks": {
            "value": 0,
            "comment": "number of diagnostic marks"
        },
        "bs_surface_1": {
            "non_symmetric": {
                "value": 0,
                "comment": "rotationally symmetrical surface"
            },
            "x_start": {
                "value": min([bs_meridian_flat_points_rs[-1][0], bs_meridian_steep_points_rs[-1][0]]),
                "comment": "x start distance from center"
            },
            "x_end": {
                "value": 0.0,
                "comment": "x end distance from center"
            },
            "junction_blend_radius": {
                "value": 0,
                "comment": "junction blend radius"
            },
            "angular_filtering": {
                "value": 0,
                "comment": "angular filtering (MAF iterations)"
            },
            "no_of_meridians": {
                "value": 0,
                "comment": "the number of meridians that constrain the surface"
            },
            "rotation_angle": {
                "value": 0,
                "comment": "the rotation angle that the first meridian will start at"
            }
        },
        "fs_surface_1": {
            "non_symmetric": {
                "value": 0,
                "comment": "rotationally symmetrical surface"
            },
            "x_start": {
                "value": max([fs_meridian_flat_points_rs[-1][0], fs_meridian_steep_points_rs[-1][0]]),
                "comment": "x start distance from center"
            },
            "x_end": {
                "value": 0.0,
                "comment": "x end distance from center"
            },
            "junction_blend_radius": {
                "value": 0,
                "comment": "junction blend radius"
            },
            "angular_filtering": {
                "value": 0,
                "comment": "angular filtering (MAF iterations)"
            },
            "no_of_meridians": {
                "value": 0,
                "comment": "the number of meridians that constrain the surface"
            },
            "rotation_angle": {
                "value": 0,
                "comment": "the rotation angle that the first meridian will start at"
            }
        }
    }
    # Determine if the design is rotationally non-symmetric
    is_non_symmetric = (
        _to_float(lab_data["RZDFlat"])  != _to_float(lab_data["RZDSteep"]) or
        _to_float(lab_data["LZAFlat"])  != _to_float(lab_data["LZASteep"]) or
        _to_float(lab_data["PECDFlat"]) != _to_float(lab_data["PECDSteep"])
    )
    if is_non_symmetric:
        header_data["non_symmetric_base"]["value"] = 1
        header_data["non_symmetric_base"]["comment"] = "non-rotationally symmetrical base surface"
        header_data["non_symmetric_front"]["value"] = 1
        header_data["non_symmetric_front"]["comment"] = "non-rotationally symmetrical front surface"
        header_data["bs_surface_1"]["non_symmetric"]["value"] = 1
        header_data["bs_surface_1"]["non_symmetric"]["comment"] = "non-rotationally symmetrical surface"
        header_data["bs_surface_1"]["no_of_meridians"]["value"] = 4
        header_data["fs_surface_1"]["non_symmetric"]["value"] = 1
        header_data["fs_surface_1"]["non_symmetric"]["comment"] = "non-rotationally symmetrical surface"
        header_data["fs_surface_1"]["no_of_meridians"]["value"] = 4
    
    #test_path = Path.cwd() / "test_dacfiles"
    logger.info("\nIs this a toric periphery lens: %s", is_non_symmetric)
    ########################

    ########################
    # Optional plotting and point file export
    if args.plot:
        logger.info("Plotting flag enabled — generating meridional plots and point files")

        write_base_surface_point_file(
            args.wo,
            header_data,
            [
                bs_meridian_flat_points_rs,
                bs_meridian_steep_points_rs,
                bs_meridian_flat_points_rs,   # repeated as per your original
                bs_meridian_steep_points_rs
            ]
        )
        write_front_surface_point_file(
            args.wo,
            header_data,
            [
                fs_meridian_flat_points_rs,
                fs_meridian_steep_points_rs,
                fs_meridian_flat_points_rs,   # repeated as per your original
                fs_meridian_steep_points_rs
            ]
        )

        plot_meridional_curves(
            [
                Curve(label="Base Surface Flat Meridian", points=bs_meridian_flat_points_rs),
                Curve(label="Front Surface Flat Meridian", points=fs_meridian_flat_points_rs),
                # Optionally add more curves if you want to compare steep meridians too:
                # Curve(label="Base Surface Steep Meridian", points=bs_meridian_steep_points_rs, linestyle="--"),
                # Curve(label="Front Surface Steep Meridian", points=fs_meridian_steep_points_rs, linestyle="--"),
            ],
            title="Optimum Infinite Orthokeratology Lens II",
            xlim=(0, 8),
            # You can also make these configurable later if needed:
            # equal_aspect=True,
            # grid=True,
            # figsize=(8, 6),
        )
        logger.info("Plotting and point file export completed")
    else:
        logger.info("Plotting skipped (run with --plot to enable)")
    ########################

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
