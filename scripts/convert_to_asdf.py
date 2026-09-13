import sys
import glob
import os
sys.path.append(r"C:\Users\obandohe\OneDrive - Stichting Deltares\Documents\DELTARES_PROJECTS\2026\09_UrbanVibe\REPOSITORY_HOST\UrbanVibe\src\urbanvibe")
from reader_h5 import convert_to_asdf


def assemble_asdf_from_h5(input_path,distance_start, distance_end,site_name,network_code, output_path):

    # Get a list of all H5 files matching the input path pattern
    h5_files = glob.glob(input_path)

    print(f"Found H5 files: {h5_files}")

    # check if output path exists, if not create it
    if not os.path.exists(output_path):
        os.makedirs(output_path)


    for h5_file in h5_files:
        convert_to_asdf(h5_file, distance_start, distance_end, output_path, network_code, site_name)
        print(f"Finished processing {h5_file}")
    print(f"Finished assembling ASDF file at {output_path}")
    return output_path



if __name__ == "__main__":


    # create arguments

    # coordinates in m
    Lamelerberweg = [9000, 10500]#[9536, 9848]
    Keienberweg = [8500, 10000]#[9160, 9424]
    Holterberweg = [7000, 8000]#[7200, 7816]

    segment = Holterberweg

    dir_name = 'Holterbergweg_fiber_distance_2036-2654'

    site_name = dir_name.split('_')[0]

    input_path = fr"P:\11212716-014-urbanvibe\01_data\smaller_shot_data_selection_CH2\{dir_name}\*.h5"
    distance_start = segment[0]
    distance_end = segment[1]
    network_code = "ubv"
    output_path = fr"P:\11212716-014-urbanvibe\03_processed_data\asdf_converted\{site_name}"


    # Assemble the ASDF file from the provided H5 files and parameters
    
    assemble_asdf_from_h5(
        input_path,
        distance_start,
        distance_end,
        site_name,
        network_code,
        output_path
    )

# run example:
# python src\urbanvibe\read_h5.py input1.h5 input2.h5 0.0 100.0 SITE_

