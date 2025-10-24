from labfile import load_lab_fields, parse_lab_file

fields = load_lab_fields("configs/lab_file.toml")
result = parse_lab_file(
    path=r"D:\Projects\XcelSpecialtyContacts\Optimum_Infinite_Orthokeratology_Lens_II\test_xcelftp\C9312150",  # or wherever your Lab File is
    fields_spec=fields,
    VALUE_COL_START=36,
)

print(result["BC"])
print(result["Dia"])
print(result["Power"])
