from pathlib import Path
import pandas as pd


def lookup_bc(csv_path: str, flat_k: float, mrs: float) -> float | None:
    """
    Look up the BC value from CRT_SKUs.csv given Flat K and MRS.

    Args:
        csv_path (str): Path to the CRT_SKUs.csv file.
        flat_k (float): Flat K value to match.
        mrs (float): MRS value to match.

    Returns:
        float | None: The BC value if found, otherwise None.
    """
    # Load CSV
    df = pd.read_csv(csv_path)

    # Filter rows matching Flat K and MRS
    match = df[(df["Flat K"] == flat_k) & (df["MRS"] == mrs)]

    if match.empty:
        return None  # No exact match found

    # Return the first BC value found
    return float(match.iloc[0]["BC"])


crt_data_path = Path("data/CRT_SKUs.csv")
bc = lookup_bc(crt_data_path, 39.0, -4.25)
if bc is not None:
    print(f"Base Curve: {bc}")
else:
    print("No match found.")
