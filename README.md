# Optimum Infinite Orthokeratology Lens II (OIOL2)

A modular, Python-driven pipeline that generates **DAC ALM**-compatible point files (Base and Front surfaces) for orthokeratology contact lenses (Lunara). The code runs on a remote Windows 11 workstation ("E") and is invoked by a lathe-attached PC ("ALM"). The ALM machine supplies arguments (e.g., work order ID, etc.), OIOL2 generates point files, returns an **exit code** to the caller, and writes the files to a shared/retrieved location.

---

## Architecture

**Roles**

* **ALM**: Lathe-side PC. Calls remote process, later retrieves generated point files.
* **E**: Remote Windows 11 workstation running a Conda env `pointfile` and the OIOL2 Python program.

**High-level flow**

1. ALM calls E with args (work order, etc.).
2. E parses the Lab File and other inputs.
3. E computes the Base/Front lens surfaces and writes **point files**.
4. E saves the files to a common shared space.
5. E returns an exit code to ALM.
6. ALM retrieves the file(s) or reports an error.

**Key modules**

* `oiol2/config.py` – Config loading/validation (TOML), defaults.
* `oiol2/labfile_parser.py` – Parse Lab Files and reference CSV/JSON tables.
* `oiol2/geometry.py` – Optical math helpers (see `geometryfunctions02.py` for the original versions of these fuctions).
* `oiol2/surface_generator.py` – Builds Base/Front surfaces from parameters.
* `oiol2/dac_pointfile_writer.py` – Create ALM/DAC-compatible point files.
* `oiol2/main.py` – CLI entry point orchestrating the pipeline.

---

## Repository layout

```text
optimum_infinite_orthokeratology_lens_ii/
├─ configs/                  # Project settings (paths, timeouts, naming)
│  ├─ config_sample.toml
│  └─ lab_file.toml
├─ data/
│  ├─ CRT_SKUs.csv
│  ├─ lens_design.toml
│  └─ lens_parameters.json
├─ docs/
│  ├─ design_mock_up_2510240940.dxf
│  ├─ Lens_Design_Summary.md
│  └─ PORTING.md
├─ labfile/
│  ├─ config.py
│  └─ parser.py
├─ logs/
├─ scripts/
│  ├─ crt_lookup.py
│  └─ simulate_alm.ps1       # Test harness that simulates the ALM PC
├─ src/
│  └─ oiol2/
│     ├─ geometry/
│     │  └─ meridional.py
│     ├─ vis/                # For plotting the meridional curves
│     │  └─ plotting.py
│     ├─ __init__.py
│     ├─ dac_pointfile_writer.py
│     ├─ geometry_core.py
│     ├─ geometryfunction02.py
│     ├─ helper.py
│     ├─ init.py
│     ├─ labfile_parser.py
│     ├─ main.py
│     ├─ surface_generator.py
│     └─ transform2d.py
├─ .gitignore
├─ environment.yml
├─ pyproject.toml            # for packaging/entry points (optional, not sure this is needed)
├─ pytest.ini
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
lab_root   = "T:\\"
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
python -m src.oiol2.main --wo 9496445 \
  --output-dir "D:/PointFiles" --config "configs/config.toml" --verbose
```
Here is how I use it locally for testing
```powershell
python -m src.oiol2.main --wo 9312150 --plot
```

**Arguments**

* `--wo` *(str/int)* – Work order ID.
* `--output-dir` *(str, optional)* – Overrides `paths.output_dir`.
* `--config` *(str, optional)* – Path to a specific TOML; defaults to `configs/config.toml`.
* `--verbose` *(optional)* More logging.
* `--plot` *(optional)* Plot curves.

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

## Roadmap

- [x] Port legacy `geometryfunctions02.py` into `oiol2/geometry.py` with unit tests
- [x] Implement robust Lab File parser with column-based extraction rules
- [x] Add CSV/JSON lookup utilities (e.g., CRT_SKUs)
- [x] Add cleanup task for old `kera*_*.txt/bin` per `cleanup.keep_hours`
- [x] Optional packaging via `pyproject.toml` with console entry-point `oiol2`
- [x] CI (GitHub Actions) for lint + tests on push
- [x] Make sure you know how to execute the code in a stand-alone configuration.  In other words what do you need to type at the command line to make the code execute.
```PowerShell
(pointfile) PS D:\Projects\XcelSpecialtyContacts\Optimum_Infinite_Orthokeratology_Lens_II> python -m src.oiol2.main --wo 9312150 --plot
python -m src.oiol2.main --wo 9496445 --plot
```
- [x] Add in the code to comment out the appropriate lines if it's rotationally symmetric
- [x] Make sure the program produces files using the new Lab Files
	- [x] Produce a test axial symetric Lab File using Configured Item 733.
	c9496445
	- [x] Produce a test non-axial symetric Lab File using Configured Item 733
	C9496422
	- [x] Make sure new `lab_file.toml` is working correctly with the code.
	- [x] Test axial symetric and non-axial symetric cases to make sure they are printing the data to the file correctly.
- [x] Change the `config.toml` so that "labfile_root = 'T:\''"
- [x] Make sure the test Lab Files are in the "T:\" location.
- [x] Put in a check to make sure adjacent point do not have the same x value when the x value is rounded to the nearest 10e-6.
- [x] Create a test PowerShell script that will launch the program with a particular work order.  We'll use this as the base for the final PowerShell script that will be used by the ALM to launch the program.
- [x] Alter the program to accept the argument of the work order.
- [x] Update README.md
- [ ] Update git repo.
- [ ] Make sure the program is updated on 081LAB20.
- [ ] Test the program using the command line on 081LAB20.
- [ ] Edit the PowerShell script so that when it is executed on GILLIARDA in executes the program on 081LAB20.  It needs to get the exit code from the program that ran on 081LAB20 and print that same exit code to the terminal.
- [ ] Edit the PowerShell script so that it copies the point files from 081LAB20 to "'D:\Projects\XcelSpecialtyContacts\Optimum_Infinite_Orthokeratology_Lens_II\test_dacfiles" when the program finishes.  Test this new file.
- [ ] Edit RGPLogin so that it produces the correct Lathe Files for this.
- [ ] Transfer the PowerShell script to Greg's PC and set-up a directory for the files to be moved to.  Make sure LSXPF is configured to point to the correct spots for the Greg'a Computer (config.toml).
- [ ] Tranfer this to an ALM and test.

