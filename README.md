# Optimum Infinite Orthokeratology Lens II (OIOL2)

A modular, Python-driven pipeline that generates **DAC ALM**-compatible point files (Base and Front surfaces) for orthokeratology contact lenses. The code runs on a remote Windows 11 workstation ("E") and is invoked by a lathe-attached PC ("ALM"). The ALM machine supplies arguments (e.g., work order ID, tool radius, output directory), OIOL2 generates point files, returns an **exit code** to the caller, and writes the files to a shared/retrieved location.

---

## Architecture

**Roles**

* **ALM**: Lathe-side PC. Calls remote process, later retrieves generated point files. (Simulated here with a PowerShell script.)
* **E**: Remote Windows 11 workstation running a Conda env `pointfile` and the OIOL2 Python program.

**High-level flow**

1. ALM calls E with args (work order, tool radius, output dir, etc.).
2. E parses the Lab File and other inputs.
3. E computes the Base/Front lens surfaces and writes **point files**.
4. E returns an exit code to ALM.
5. ALM retrieves the file(s) or reports an error.

**Key modules**

* `oiol2/config.py` – Config loading/validation (TOML), defaults.
* `oiol2/labfile_parser.py` – Parse Lab Files and reference CSV/JSON tables.
* `oiol2/geometry.py` – Optical math helpers (moved from `geometryfunctions02.py`).
* `oiol2/surface_generator.py` – Builds Base/Front surfaces from parameters.
* `oiol2/dac_pointfile_writer.py` – Emits ALM/DAC-compatible point files.
* `oiol2/main.py` – CLI entry point orchestrating the pipeline.

---

## Repository layout

```text
optimum_infinite_orthokeratology_lens_ii/
├─ src/
│  └─ oiol2/
│     ├─ __init__.py
│     ├─ main.py
│     ├─ config.py
│     ├─ labfile_parser.py
│     ├─ geometry.py
│     ├─ surface_generator.py
│     └─ dac_pointfile_writer.py
├─ configs/
│  └─ config.toml            # Project settings (paths, timeouts, naming)
├─ data/
│  ├─ CRT_SKUs.csv
│  └─ lens_parameters.json
├─ scripts/
│  └─ simulate_alm.ps1       # Test harness that simulates the ALM PC
├─ test_dacfiles/            # simulation for \\xcelprod04\dacfiles a.k.a. U:\ drive
├─ test_xcelftp/             # simulation for \\xcelprod04\xcelftp a.k.a. T:\ drive
│  └─ C9359766               # Test Lab File
├─ tests/
│  └─ test_smoke.py          # Minimal sanity tests
├─ .gitignore
├─ environment.yml
├─ pyproject.toml            # for packaging/entry points (optional, not sure this is needed)
└─ README.md                 # this file
```

## Installation & environment

### 1) Create the Conda env

```powershell
conda env create -f environment.yml
conda activate pointfile
```

**`environment.yml`** (example)

```yaml
name: pointfile
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - numpy
  - pandas
  - tomllib
  - click  # CLI ergonomics
  - pytest
```

## Configuration

All runtime settings live in `configs/config.toml`. Example:

```toml
[paths]
# Where E writes the finished point files
output_dir = "D:\\Projects\\XcelSpecialtyContacts\\Optimum_Infinite_Orthokeratology_Lens_II\\test_dacfiles"
# Base folder where Lab Files live (can be a share)
lab_root   = "D:\\Projects\\XcelSpecialtyContacts\\Optimum_Infinite_Orthokeratology_Lens_II\\test_dacfiles"
# Optional temp working dir
work_dir   = "D:\\Projects\\XcelSpecialtyContacts\\Optimum_Infinite_Orthokeratology_Lens_II\\src\\oiol2"

[naming]
# How output files are named
base_pattern  = "{wo}.V5B"
front_pattern = "{wo}.V5F"

[timeouts]
# End-to-end generation cap (seconds)
job_timeout_s = 300

[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR
file  = "D:\\Projects\\XcelSpecialtyContacts\\Optimum_Infinite_Orthokeratology_Lens_II\\logs\\oiol2.log"

[cleanup]
# Delete files older than this many hours in output_dir
keep_hours = 0  # 0 means to keep them indefinately
```
---

## Command-line usage (on E)

```powershell
# From repo root with env active
python -m oiol2 --wo 8280256 --tool-rad 0.501 --labfile X8280256 \
  --output-dir "D:/PointFiles" --config "configs/config.toml" --verbose
```

**Arguments**

* `--wo` *(str/int)* – Work order ID.
* `--output-dir` *(str, optional)* – Overrides `paths.output_dir`.
* `--config` *(str, optional)* – Path to a specific TOML; defaults to `configs/config.toml`.
* `--verbose` – *(optional)* More logging.

**Exit codes**

* `0` – Success (both Base and Front point files written).
* `1` – Success (Base point file written).
* `2` – Success (Base point file written).
* `10` – Input error (missing Lab File, bad args, config invalid).
* `20` – Computation error (geometry/surface math failed).
* `30` – Output error (cannot write files, permissions/space).
* `40` – Timeout (job exceeded `timeouts.job_timeout_s`).
* `50` – Unknown/unhandled exception.

---

## Simulating ALM (PowerShell)

`scripts/simulate_alm.ps1` runs on ALM (or any Windows box) and **remotely** invokes OIOL2 on E via PowerShell Remoting. Adjust names/paths for your environment.

```powershell
param(
  [Parameter(Mandatory)] [string]$TargetComputer,    # e.g. "EPC01"
  [Parameter(Mandatory)] [string]$WorkOrder,         # e.g. "8280256"
  [Parameter()] [string]$OutputDir = "D:/PointFiles",
  [Parameter()] [string]$RepoRoot  = "D:/Projects/OIOL2",
  [Parameter()] [string]$CondaEnv  = "pointfile"
)

$script = {
  param($wo,$out,$root,$envName)
  $ErrorActionPreference = 'Stop'
  # Activate env and run the module
  conda.exe run -n $envName python -m oiol2 --wo $wo `
    --output-dir $out --config (Join-Path $root 'configs/config.toml')
  exit $LASTEXITCODE
}

Invoke-Command -ComputerName $TargetComputer -ScriptBlock $script -ArgumentList `
  $WorkOrder,$OutputDir,$RepoRoot,$CondaEnv -ErrorAction Stop

$code = $LASTEXITCODE
Write-Host "Remote job exit code: $code"

if ($code -ne 0) {
  throw "Point file generation failed with exit code $code"
}

# If needed, pull files from share or remote (robocopy/example)
```

> If WinRM isn’t available, you can swap to SSH: `ssh EPC01 "conda run -n pointfile python -m oiol2 ..."`.

---

## Development notes

* **Logging**: All steps are logged to console and optional log file. Use `--verbose` or set `logging.level = "DEBUG"`.
* **Determinism**: Geometry functions are pure and unit-tested. Add fixtures in `tests/`.
* **Performance**: For large point clouds, prefer NumPy arrays and vectorized math.
* **Safety**: Always validate inputs (ranges, nulls). Abort on invalid lab data.
* **Backwards-compat**: Keep a thin wrapper to accept legacy flags/paths used by ALM.

---

## Minimal code scaffolding

**`src/oiol2/main.py` (excerpt)**

```python
from __future__ import annotations
import sys, argparse, logging, time
from .config import load_config
from .labfile_parser import parse_lab_file
from .surface_generator import build_base_surface, build_front_surface
from .dac_pointfile_writer import write_point_file

EXIT = {
    'OK': 0,
    'INPUT': 10,
    'MATH': 20,
    'OUTPUT': 30,
    'TIMEOUT': 40,
    'UNKNOWN': 50,
}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--wo', required=True)
    p.add_argument('--tool-rad', type=float, required=True)
    p.add_argument('--labfile', required=True)
    p.add_argument('--output-dir')
    p.add_argument('--config', default='configs/config.toml')
    p.add_argument('--verbose', action='store_true')
    return p.parse_args()

def main() -> int:
    try:
        args = parse_args()
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                            format='%(asctime)s %(levelname)7s %(message)s')
        cfg = load_config(args.config, override_output=args.output_dir)
        t0 = time.time()

        lab_path = cfg.resolve_labfile(args.labfile)
        lab_data = parse_lab_file(lab_path)

        base = build_base_surface(lab_data, tool_radius=args.tool_rad)
        front = build_front_surface(lab_data)

        out_b = cfg.make_output_path('base', args.wo, args.tool_rad)
        out_f = cfg.make_output_path('front', args.wo, args.tool_rad)
        write_point_file(out_b, base)
        write_point_file(out_f, front)

        if time.time() - t0 > cfg.timeouts.job_timeout_s:
            logging.error('Job exceeded timeout.')
            return EXIT['TIMEOUT']

        logging.info('Done. Wrote %s and %s', out_b, out_f)
        return EXIT['OK']
    except FileNotFoundError as e:
        logging.exception('Input error: %s', e)
        return EXIT['INPUT']
    except ValueError as e:
        logging.exception('Computation error: %s', e)
        return EXIT['MATH']
    except OSError as e:
        logging.exception('Output error: %s', e)
        return EXIT['OUTPUT']
    except Exception:
        logging.exception('Unknown failure')
        return EXIT['UNKNOWN']

if __name__ == '__main__':
    sys.exit(main())
```

---

## Testing

```powershell
pytest -q
```

* `tests/test_smoke.py` should verify that dummy Lab Files run end-to-end and produce two non-empty files under a temp output dir.

---

## Roadmap

* [ ] Port legacy `geometryfunctions02.py` into `oiol2/geometry.py` with unit tests
* [ ] Implement robust Lab File parser with column-based extraction rules
* [ ] Add CSV/JSON lookup utilities (e.g., CRT_SKUs)
* [ ] Add cleanup task for old `kera*_*.txt/bin` per `cleanup.keep_hours`
* [ ] Optional packaging via `pyproject.toml` with console entry-point `oiol2`
* [ ] CI (GitHub Actions) for lint + tests on push

---

## License

TBD (private/internal). Add a license if/when needed.
