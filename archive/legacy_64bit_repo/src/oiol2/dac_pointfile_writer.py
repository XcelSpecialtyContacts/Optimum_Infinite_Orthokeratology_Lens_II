# src/oiol2/dac_pointfile_writer.py

from __future__ import annotations
from pathlib import Path
from typing import List
import numpy as np

def write_base_surface_point_file(
    wo: str,
    header_data: dict,
    meridians: List[np.ndarray],
):
    """
    Creates a the base surface DAC ALM point file.
    """
    filename = wo + ".V5B"
    filepath = Path.cwd() / "test_dacfiles" / filename
    try:
        # How many meridional lines of points will need to be processed
        if header_data['non_symmetric_base']['value'] == 0:
            meridional_line_count = 1
        else:
            meridional_line_count = len(meridians)
        
        # Open point file in write mode ('w' creates the file if it doesn't exist)
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"{'BR':<20}\\ back side\n") # header line 1
            file.write(f"{str(header_data['non_symmetric_base']['value']):<20}\\ {str(header_data['non_symmetric_base']['comment'])}\n") # header line 2
            file.write(f"{str(header_data['no_of_base_surfaces']['value']):<20}\\ {str(header_data['no_of_base_surfaces']['comment'])}\n") # header line 3
            file.write(f"{str(header_data['BC_horizontal']['value']):<20}\\ {str(header_data['BC_horizontal']['comment'])}\n") # header line 4
            file.write(f"{str(header_data['BC_vertical']['value']):<20}\\ {str(header_data['BC_vertical']['comment'])}\n") # header line 5
            file.write(f"{str(header_data['BCOZ_dia']['value']):<20}\\ {str(header_data['BCOZ_dia']['comment'])}\n") # header line 6
            file.write(f"{str(header_data['lens_dia']['value']):<20}\\ {str(header_data['lens_dia']['comment'])}\n") # header line 7
            file.write(f"{str(header_data['no_of_parts_to_cut']['value']):<20}\\ {str(header_data['no_of_parts_to_cut']['comment'])}\n") # header line 8
            file.write(f"{str(header_data['lens_sag_bs']['value']):<20}\\ {str(header_data['lens_sag_bs']['comment'])}\n") # header line 9
            file.write(f"\\ -- SURFACE DEFINITION #1 --\n") # header line 10
            file.write(f"{str(header_data['bs_surface_1']['non_symmetric']['value']):<20}\\ {str(header_data['bs_surface_1']['non_symmetric']['comment'])}\n") # header line 11
            file.write(f"{str(header_data['bs_surface_1']['x_start']['value']):<20}\\ {str(header_data['bs_surface_1']['x_start']['comment'])}\n") # header line 12
            file.write(f"{str(header_data['bs_surface_1']['x_end']['value']):<20}\\ {str(header_data['bs_surface_1']['x_end']['comment'])}\n") # header line 13
            file.write(f"{str(header_data['bs_surface_1']['junction_blend_radius']['value']):<20}\\ {str(header_data['bs_surface_1']['junction_blend_radius']['comment'])}\n") # header line 14
            if header_data["non_symmetric_base"]["value"] == 0: # comment out the next three lines if the surfaces is axial symetric
                file.write(f"\{str(header_data['bs_surface_1']['angular_filtering']['value']):<20}\\ {str(header_data['bs_surface_1']['angular_filtering']['comment'])}\n") # header line 15
                file.write(f"\{str(header_data['bs_surface_1']['no_of_meridians']['value']):<20}\\ {str(header_data['bs_surface_1']['no_of_meridians']['comment'])}\n") # header line 16
                file.write(f"\{str(header_data['bs_surface_1']['rotation_angle']['value']):<20}\\ {str(header_data['bs_surface_1']['rotation_angle']['comment'])}\n") # header line 17
            else:
                file.write(f"{str(header_data['bs_surface_1']['angular_filtering']['value']):<20}\\ {str(header_data['bs_surface_1']['angular_filtering']['comment'])}\n") # header line 15
                file.write(f"{str(header_data['bs_surface_1']['no_of_meridians']['value']):<20}\\ {str(header_data['bs_surface_1']['no_of_meridians']['comment'])}\n") # header line 16
                file.write(f"{str(header_data['bs_surface_1']['rotation_angle']['value']):<20}\\ {str(header_data['bs_surface_1']['rotation_angle']['comment'])}\n") # header line 17
            #file.write(f"\\ --- radial definition ---\n") # header line 18
            for n in range(meridional_line_count):
                meridian = meridians[n]
                rev = meridian[::-1]   # last → first

                # number of points in this meridian
                file.write(
                    f"{len(rev):<20}\\ number of points in meridian\n"
                )

                # write x ; y pairs
                for x, y in rev:
                    file.write(f"{x:.10f} ; {y:.10f}\n")

        print(f"File '{filepath}' created successfully.")
    except PermissionError:
        print(f"Error: Permission denied to create '{filepath}'.")
    except OSError as e:
        print(f"OS error occurred: {e}")


def write_front_surface_point_file(
    wo: str,
    header_data: dict,
    meridians: List[np.ndarray],
):
    """
    Creates a the base surface DAC ALM point file.
    """
    filename = wo + ".V5F"
    filepath = Path.cwd() / "test_dacfiles" / filename
    try:
        # How many meridional lines of points will need to be processed
        if header_data['non_symmetric_base']['value'] == 0:
            meridional_line_count = 1
        else:
            meridional_line_count = len(meridians)
        
        # Open point file in write mode ('w' creates the file if it doesn't exist)
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"{'FR':<20}\\ front side\n") # header line 1
            file.write(f"{str(header_data['non_symmetric_front']['value']):<20}\\ {str(header_data['non_symmetric_front']['comment'])}\n") # header line 2
            file.write(f"{str(header_data['no_of_front_surfaces']['value']):<20}\\ {str(header_data['no_of_front_surfaces']['comment'])}\n") # header line 3
            file.write(f"{str(header_data['FC_horizontal']['value']):<20}\\ {str(header_data['FC_horizontal']['comment'])}\n") # header line 4
            file.write(f"{str(header_data['FC_vertical']['value']):<20}\\ {str(header_data['FC_vertical']['comment'])}\n") # header line 5
            file.write(f"{str(header_data['FCOZ_dia']['value']):<20}\\ {str(header_data['BCOZ_dia']['comment'])}\n") # header line 6
            file.write(f"{str(header_data['lens_dia']['value']):<20}\\ {str(header_data['lens_dia']['comment'])}\n") # header line 7
            file.write(f"{str(header_data['no_of_parts_to_cut']['value']):<20}\\ {str(header_data['no_of_parts_to_cut']['comment'])}\n") # header line 8
            file.write(f"{str(header_data['ct']['value']):<20}\\ {str(header_data['ct']['comment'])}\n") # header line 9
            file.write(f"{str(header_data['no_of_diag_marks']['value']):<20}\\ {str(header_data['no_of_diag_marks']['comment'])}\n") # header line 10
            file.write(f"\\ -- SURFACE DEFINITION #1 --\n") # header line 11
            file.write(f"{str(header_data['fs_surface_1']['non_symmetric']['value']):<20}\\ {str(header_data['fs_surface_1']['non_symmetric']['comment'])}\n") # header line 12
            file.write(f"{str(header_data['fs_surface_1']['x_start']['value']):<20}\\ {str(header_data['fs_surface_1']['x_start']['comment'])}\n") # header line 13
            file.write(f"{str(header_data['fs_surface_1']['x_end']['value']):<20}\\ {str(header_data['fs_surface_1']['x_end']['comment'])}\n") # header line 14
            file.write(f"{str(header_data['fs_surface_1']['junction_blend_radius']['value']):<20}\\ {str(header_data['fs_surface_1']['junction_blend_radius']['comment'])}\n") # header line 15
            if header_data["non_symmetric_front"]["value"] == 0: # comment out the next three lines if the surfaces is axial symetric
                file.write(f"\{str(header_data['fs_surface_1']['angular_filtering']['value']):<20}\\ {str(header_data['fs_surface_1']['angular_filtering']['comment'])}\n") # header line 16
                file.write(f"\{str(header_data['fs_surface_1']['no_of_meridians']['value']):<20}\\ {str(header_data['fs_surface_1']['no_of_meridians']['comment'])}\n") # header line 17
                file.write(f"\{str(header_data['fs_surface_1']['rotation_angle']['value']):<20}\\ {str(header_data['fs_surface_1']['rotation_angle']['comment'])}\n") # header line 18
            else:
                file.write(f"{str(header_data['fs_surface_1']['angular_filtering']['value']):<20}\\ {str(header_data['fs_surface_1']['angular_filtering']['comment'])}\n") # header line 16
                file.write(f"{str(header_data['fs_surface_1']['no_of_meridians']['value']):<20}\\ {str(header_data['fs_surface_1']['no_of_meridians']['comment'])}\n") # header line 17
                file.write(f"{str(header_data['fs_surface_1']['rotation_angle']['value']):<20}\\ {str(header_data['fs_surface_1']['rotation_angle']['comment'])}\n") # header line 18
            file.write(f"\\ --- radial definition ---\n") # header line 19
            for n in range(meridional_line_count):
                meridian = meridians[n]
                rev = meridian[::-1]   # last → first

                # number of points in this meridian
                file.write(
                    f"{len(rev):<20}\\ number of points in meridian\n"
                )

                # write x ; y pairs
                for x, y in rev:
                    file.write(f"{x:.10f} ; {y + header_data['ct']['value']:.10f}\n")

        print(f"File '{filepath}' created successfully.")
    except PermissionError:
        print(f"Error: Permission denied to create '{filepath}'.")
    except OSError as e:
        print(f"OS error occurred: {e}")
