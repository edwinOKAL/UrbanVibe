import numpy as np
from obspy import UTCDateTime
import pandas as pd
from obspy import read
import sys
sys.path.append(r"C:\Users\obandohe\OneDrive - Stichting Deltares\Documents\DELTARES_PROJECTS\2026\09_UrbanVibe\REPOSITORY_HOST\UrbanVibe\src\urbanvibe")
from reader_h5 import combine_streams
import os


def slice_time_segment(all_st, reference_time, dist_range,output_dir):

    start_time = UTCDateTime(reference_time)  # example start time
    end_time = start_time + 5 #5  # example end time, 60 seconds after start time
    st_window_sel = all_st.slice(starttime=start_time, endtime=end_time)
    #st_window_sel.plot(type='section', orientation='vertical', show=False, figsize=(10, 6))

    # Customization for the plot
    fig = st_window_sel.plot(type='section', orientation='vertical', show=True,time_down=True, figsize=(10, 6))

    # convert '-' and ":" to "_" for the filename
    reference_time_safe = reference_time.replace("-", "_").replace(":", "_")

    fig.savefig(fr"{output_dir}/selected_shot_at_{dist_range[0]}m_{dist_range[1]}m_at_{reference_time_safe}.png")

    # remove mask from the traces in the selected window
    for tr in st_window_sel:
        tr.data = np.ma.filled(tr.data, fill_value=0)

    return st_window_sel



def extract_individual_shots(all_st, df_segments, dist_range,output_dir):
    """
    Extract individual shots from the stream based on reference times and distance range.

    Parameters
    ----------
    all_st : obspy.Stream
        The complete ObsPy stream containing all traces.
    df_segments : pandas.DataFrame
        DataFrame containing the reference times for the shots.
    dist_range : tuple
        The distance range (start, end) for the selected shots.
    """
    # check if the output directory exists, if not, create it
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)


    for reference_time in df_segments['ref_time']:
        st_window_sel = slice_time_segment(all_st, reference_time, dist_range, output_dir)
        # Optionally, save the trimmed stream to a new file
        reference_time_safe = reference_time.replace("-", "_").replace(":", "_")
        st_window_sel.write(fr"{output_dir}/selected_shot_at_{dist_range[0]}m_{dist_range[1]}m_at_{reference_time_safe}.mseed")


if __name__ == "__main__":

    # Example usage

    all_st = read("../data/all_traces.mseed")
    df_segments = pd.read_csv("../data/segments.csv")
    dist_range = (7000, 8000)  # example distance range
    all_st = combine_streams(paths="../data/all_traces.asdf", distance=dist_range)
    extract_individual_shots(all_st, df_segments, dist_range, output_dir="../selected_shots")

