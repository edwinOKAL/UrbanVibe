import febus_optics_lib.reader as reader
import pyasdf
import obspy
import numpy as np
from datetime import datetime
import os
import glob
from plotting import plot_selected_segment
from obspy import Stream

def read_h5_file(h5_file,timestamp_start=None,timestamp_end=None,):
    """
    Read h5file using FEBUS functions for given distance range and time range

    Returns:
        tr (np.ndarray): 2D array of signal data (time x distance)
        dist (np.ndarray): Distance vector
        time (np.ndarray): Time vector
        props (dict): Dictionary of H5 file properties
    """
    instance = reader.H5ReaderDas(h5_file)
    props = instance.param_dict
    zone = props['list_zones'][0]

    if timestamp_start is None:
        timestamp_start = props[zone]['timestamp_start']
    if timestamp_end is None:
        timestamp_end = props[zone]['timestamp_end']

    distance_start = props[zone]['distance_start']
    distance_end = props[zone]['distance_end']

    
    # use absolute timestamps for time selection
    dist_type = "meter"  # Use distance in meters
    time_type = "timestamp"  # Use absolute timestamps

    concat_results = instance.extract_concat(
        from_time=timestamp_start, to_time=timestamp_end, time_type=time_type,
        from_dist=distance_start, to_dist=distance_end, dist_type=dist_type, zones=zone)


    # Extract the data, distance vector, and time vector
    tr = concat_results[zone]["data"]  # Signal data: 2D array (time x distance)
    dist = concat_results[zone]["distance_vect"]  # Distance vector
    time = concat_results[zone]["time_vect"]  # Time vector

    return tr, dist, time, props



def get_acquisition_props(props, zone=None):
    if zone is None:
        zone = props['list_zones'][0]
    return {
        'timestamp_start': props[zone]['timestamp_start'],
        'timestamp_end': props[zone]['timestamp_end'],
        'sampling_rate': props[zone]['sampling_rate'],
        'dx': props[zone]['distance_spacing'],
        'zone': zone
    }



def convert_to_asdf(h5_file, distance_start, distance_end, output_path, network_code, site_name, plot=True):

    """
    Convert a segment of an H5 file to an ASDF file.

    Args:
        h5_file (str): Path to the input H5 file.
        distance_start (float): Start of the distance range.
        distance_end (float): End of the distance range.
        output_path (str): Path to the output ASDF file.
        network_code (str): Network code for the ASDF file.
        site_name (str): Site name for the ASDF file.
        plot (bool): Whether to plot the selected segment. Default is True.

    Returns:
        pyasdf.ASDFDataSet: The created ASDF dataset.
    """

    # get h5 file record
    tr_full, dist_full, time, props = read_h5_file(h5_file)

    if plot:
        print(f"Plotting selected segment and saving to {output_path}")
        save_full = os.path.join(output_path, h5_file.split('\\')[-1].replace('.h5', f'_full_record.png'))

        # print save path for the plot
        print(f"Saving plot of full records to {save_full}")

        plot_selected_segment(tr_full[::100], dist_full, time[0], time[-1], save_path=save_full)


    # select the segment of interest based on the provided distance range
    dist_mask = (dist_full >= distance_start) & (dist_full <= distance_end)
    tr = tr_full[:, dist_mask]
    dist = dist_full[dist_mask]

    if plot:
        print(f"Plotting selected segment and saving to {output_path}")
        save_path = os.path.join(output_path, h5_file.split('\\')[-1].replace('.h5', f'_selected_segment_at{distance_start}m_{distance_end}m.png'))

        # print save path for the plot
        print(f"Saving plot of selected segment to {save_path}")

        plot_selected_segment(tr, dist, time[0], time[-1], save_path=save_path)


    acq_props = get_acquisition_props(props)
    fs = acq_props['sampling_rate']
    start_time = acq_props['timestamp_start']

    # get acquisition properties
    acq_props = get_acquisition_props(props)
    fs = acq_props['sampling_rate']
    start_time = acq_props['timestamp_start']

    # output_asdf_save
    output_asdf_save = os.path.join(output_path, h5_file.split('\\')[-1].replace('.h5', f'_selected_segment_at{distance_start}m_{distance_end}m.asdf'))
    print(f"Saving ASDF file to {output_asdf_save}")

    # Initialize your output ASDF file
    with pyasdf.ASDFDataSet(output_asdf_save, compression="gzip-3") as ds:
        
        # Loop over the channels you want to store (e.g., first 100 channels)
        for i, location in enumerate(dist):

            # 1. Isolate the 1D time-series data for this channel
            channel_data = tr[:, i].astype(np.float32)
            
            # 2. Build the ObsPy trace header information
            stats = {
                'network': network_code,
                'station': f"{location/1000}km",  # Map channel index to station name
                'location': site_name,
                'channel': f'CH_{i}',             # Hydrophone/Strain-rate code
                'sampling_rate': fs,
                'starttime': start_time
            }
            
            # 3. Instantiate an ObsPy Stream
            stream = obspy.Stream(traces=[obspy.Trace(data=channel_data, header=stats)])
            
            # 4. Stream it directly into the ASDF HDF5 archive
            # The tag groups related processing runs together
            ds.add_waveforms(stream, tag="raw_das_recording")



def combine_streams(paths, distance):
    """
    Combine multiple ASDF datasets into a single ObsPy Stream.

    Parameters
    ----------
    paths : list of str
        List of paths to the ASDF files.
    distance : array-like
        Array of distances corresponding to each channel.

    Returns
    -------
    all_st : obspy.Stream
        Combined ObsPy Stream containing all traces from the input ASDF files.
    """

    # define an empty stream to hold all traces from all ASDF files
    all_st = Stream()

    # iterate over each ASDF file and extract the waveforms
    for path in paths:
        ds = pyasdf.ASDFDataSet(path)

        st = Stream()
        for i, channel in enumerate(ds.waveforms):
            tr = channel.raw_das_recording
            tr[0].stats['distance'] = distance[i] # distance is required for plotting
            st += tr

        # merge individual stream into the all_st stream
        st.merge(method=1)  # merge individual stream before adding to all_st
        all_st += st

    # merge all streams into a single stream
    all_st.merge(method=1)  # merge traces with the same id
    return all_st


