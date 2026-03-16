# tests/test_parser.py
from pathlib import Path
from labfile import load_lab_fields, parse_lab_file

LAB_TEXT = """\
007    OD                            Right Eye
060    BC                             8.60
080    PWR                            -2.50
110    DIA                            10.50
120    NOTE                           *Calculated
130    EMPTY                          
"""

TOML = """\
[lab_fields.OD_OS]
seg = '007'
title = 'Lens R / L'

[lab_fields.BC]
seg = '060'
title = 'Base Curve'

[lab_fields.Dia]
seg = '110'
title = 'Diameter'

[lab_fields.Power]
seg = '080'
title = 'Power'

[lab_fields.Note]
seg = '120'
title = 'Note'

[lab_fields.Empty]
seg = '130'
title = 'Empty'
"""

def test_basic_parse(tmp_path: Path):
    lab_path = tmp_path / "lab.txt"
    toml_path = tmp_path / "lab_fields.toml"
    lab_path.write_text(LAB_TEXT, encoding="utf-8", newline="\n")
    toml_path.write_text(TOML, encoding="utf-8", newline="\n")

    fields = load_lab_fields(toml_path)
    res = parse_lab_file(lab_path, fields, VALUE_COL_START=36)

    assert res["BC"]["value"] == "8.60"
    assert res["Dia"]["value"] == "10.50"
    assert res["Power"]["value"] == "-2.50"
    # "*Calculated" -> empty string
    assert res["Note"]["value"] == ""
    # truly empty right of column 36 -> empty string
    assert res["Empty"]["value"] == ""
    # seg present; title correct passthrough
    assert res["OD_OS"]["title"] == "Lens R / L"
