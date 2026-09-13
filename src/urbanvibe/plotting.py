import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_selected_segment(data, distance, timestamp_start, timestamp_end, save_path=None):

    """
    Plot a selected segment of data.

    Args:
        data (numpy.ndarray): 2D array of the data to plot.
        distance (numpy.ndarray): 1D array of distance values corresponding to the columns of the data.
        timestamp_start (float): Start time of the segment.
        timestamp_end (float): End time of the segment.
        save_path (str, optional): Path to save the plot. If None, the plot will be displayed instead.

    Returns:
        None
    """

    figure = plt.figure(figsize=(12, 5))

    extent = [distance.min(), distance.max(), timestamp_start, timestamp_end]

    plt.imshow(data, aspect='auto', vmin=-5000, vmax=5000, cmap='seismic', extent=extent)
    plt.colorbar()
    plt.xlabel('Distance')
    plt.ylabel('Time')
    plt.title('Selected Segment')

    # Set the y-axis to display time in ascending order
    plt.gca().invert_yaxis()

    # save the selected segment figure if a save path is provided
    if save_path is not None:
        figure.savefig(save_path)

    # optionally display the figure if not saving
    if save_path is None:
        plt.show()

    plt.close(figure)