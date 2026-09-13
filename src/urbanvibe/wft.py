
"""
Multiple wavefield transformations for active-source (i.e., MASW) measurements including:
frequency-wavenumber (Nolet and Panza, 1976),
phase-shift (Park, 1998),
slant-stack (McMechan and Yedlin, 1981), and
frequency domain beamformer (Zywicki 1999)

"""


import numpy as np
from abc import ABC, abstractclassmethod
import logging
import warnings
import matplotlib.pyplot as plt
from scipy import special
import math

def _frequency_keep_ids(frequencies, fmin, fmax, multiple):
    """Ids to keep between [fmin, fmax] (inclusive) by multiple."""
    fmin_ids = np.argmin(np.abs(frequencies-fmin))
    fmax_ids = np.argmin(np.abs(frequencies-fmax))
    keep_ids = range(fmin_ids, (fmax_ids+1), multiple)
    return keep_ids


def _spatiospectral_correlation_matrix(tmatrix,nfft, frq_ids=None, weighting=None):
        """Compute the spatiospectral correlation matrix.
        Parameters
        ----------
        tmatrix : ndarray
            Three-dimensional matrix of shape
            `(samples_per_block, nblocks, nchannels)`.
        fmin, fmax : float, optional
            Minimum and maximum frequency of interest.
        Returns
        -------
        ndarray
            Of size `(nchannels, nchannels, nfrqs)` containing the
            spatiospectral correlation matrix.
        """
        # TODO (jpv): Rewrite docstring.
        nchannels, samples_per_block, nblocks = tmatrix.shape

        # Perform FFT
        transform = np.fft.fft(tmatrix,nfft,axis=1)

        # Trim FFT
        if frq_ids is not None:
            transform = transform[:, frq_ids, :]

        # Define weighting matrix
        if weighting == "invamp":
            _, nfrqs, _ = transform.shape
            weighting = 1/np.abs(np.mean(transform, axis=-1))

            for i in range(nfrqs):
                w = weighting[:, i]
                for b in range(nblocks):
                    transform[:, i, b] *= w

        # Calculate spatiospectral correlation matrix
        nchannels, nfrqs, nblocks = transform.shape
        spatiospectral = np.empty((nchannels, nchannels, nfrqs), dtype=complex)
        scm = np.zeros((nchannels, nchannels), dtype=complex)
        tslice = np.zeros((nchannels, 1), dtype=complex)
        tslice_h = np.zeros((1, nchannels), dtype=complex)
        for i in range(nfrqs):
            scm[:, :] = 0
            for j in range(nblocks):
                tslice[:, 0] = transform[:, i, j]
                tslice_h[0, :] = np.conjugate(tslice)[:, 0]
                scm += np.dot(tslice, tslice_h)
            scm /= nblocks
            spatiospectral[:, :, i] = scm[:]

        return spatiospectral


def sl_stack(tmatrix,offsets,fs,velocities,settings):
        """Perform a slant-stack on the given wavefield data.
        Parameters
        ----------
        array : Array1d
            One-dimensional array object.
        velocities : ndarray
            One-dimensional array of trial velocities.
        Returns
        -------
        tuple
            Of the form `(tau, slant_stack)` where `tau` is an ndarray
            of the attempted intercept times and `slant_stack` are the
            slant-stacked waveforms.
        """
        #tmatrix, position = array._flipped_tseries_and_offsets()


        nrec, nsamps = np.shape(tmatrix)
        position = offsets
        position = np.array(position)
        position -= np.min(position)
        nchannels = nrec
        diff = position[1:] - position[:-1]
        diff = diff.reshape((len(diff), 1))
        dt = 1/fs
        npts = nsamps
        ntaus = npts - int(np.max(position)*np.max(1/velocities)/dt) - 1

        print(ntaus)

        slant_stack = np.empty((len(velocities), ntaus))
        rows = np.tile(np.arange(nchannels).reshape(nchannels, 1), (1, ntaus))
        cols = np.tile(np.arange(ntaus).reshape(1, ntaus), (nchannels, 1))

        pre_float_indices = position.reshape(nchannels, 1)/dt
        previous_lower_indices = np.zeros((nchannels, 1), dtype=int)
        for i, velocity in enumerate(velocities):
            float_indices = pre_float_indices/velocity
            lower_indices = np.array(float_indices, dtype=int)
            delta = float_indices - lower_indices
            cols += lower_indices - previous_lower_indices
            amplitudes = tmatrix[rows, cols] * \
                (1-delta) + tmatrix[rows, cols+1]*delta
            integral = 0.5*diff*(amplitudes[1:, :] + amplitudes[:-1, :])
            summation = np.sum(integral, axis=0)
            slant_stack[i, :] = summation

            previous_lower_indices[:] = lower_indices

        # taus = np.arange(ntaus)*dt
        # return (taus, slant_stack)



        # Perform slant-stack
        dt = 1/fs     
        fmax_nyq = (1/dt)/2
        freq_diff = 0.5
        res = math.log2((2*(fmax_nyq/(freq_diff))))
        nfft = int(math.pow(2,res))    
        _df = fmax_nyq/(nfft/2)  

        # u(x,t) -> FFT -> U(x,f).
        # Frequency vector.
        frqs = np.arange(nsamps)*_df

        # Fourier Transform of the slant-stack
        power = np.fft.fft(slant_stack, nfft)

        # Trim and downsample frequencies.
        keep_ids = _frequency_keep_ids(frqs,
                                           settings["fmin"],
                                           settings["fmax"],
                                           1)

        

        return (frqs[keep_ids], power[:, keep_ids])



def phase_shift(tmatrix, offsets, fs, velocities, settings):
        """Perform the Phase-Shift Transform.
        Parameters
        ----------
        array : Array1D
            Instance of `Array1D`.
        velocities : ndarray
            Vector of trial velocities.
        settings : dict
            `dict` with processing settings.
        Returns
        -------
        tuple
            Of the form `(frequencies, power)`.
        """
        # Flip reference frame (if required).
        nrec, nsamps = np.shape(tmatrix)

        dt = 1/fs     
        fmax_nyq = (1/dt)/2
        freq_diff = 0.5
        res = math.log2((2*(fmax_nyq/(freq_diff))))
        nfft = int(math.pow(2,res))    
        _df = fmax_nyq/(nfft/2)  

        # u(x,t) -> FFT -> U(x,f).
        fft = np.fft.fft(tmatrix,nfft)
        # Frequency vector.
        frqs = np.arange(nsamps)*_df

        # Trim and downsample frequencies.
        keep_ids = _frequency_keep_ids(frqs,
                                           settings["fmin"],
                                           settings["fmax"],
                                           1)
        frequencies = frqs[keep_ids]

        # Integrate across the array offsets.
        power = np.empty((len(velocities), len(frequencies)))
        dx = offsets[1:] - offsets[:-1]
        for row, vel in enumerate(velocities):
            exponent = 1j * 2*np.pi/vel * offsets
            for col, (f_index, frq) in enumerate(zip(keep_ids, frequencies)):
                shift = np.exp(exponent*frq)
                inner = shift*fft[:, f_index]/np.abs(fft[:, f_index])
                integral = np.abs(np.sum(0.5*dx*(inner[:-1] + inner[1:])))
                power[row, col] = integral

        return (frequencies, power)



def fdbfm(tmatrix,offsets, fs, velocities, settings):
    """Perform Frequency-Domain Beamforming.
    Parameters
    ----------
    array : Array1D
        Instance of `Array1D`.
    velocities : ndarray
        Vector of trial velocities.
    settings : dict
        `dict` with processing settings.
    Returns
    -------
    tuple
        Of the form `(frequencies, power)`.
    """
    # Flip reference frame (if required).
    #tmatrix, offsets = array._flipped_tseries_and_offsets()

    # Reshape to 3D array, for calculating sscm.
    #sensor = array.sensors[0]

    nrec, nsamps = np.shape(tmatrix)
    tmatrix = tmatrix.reshape(nrec, nsamps, 1)

    # Frequency vector
    #frqs = np.arange(sensor.nsamples)*sensor._df

    dt = 1/fs     
    fmax_nyq = (1/dt)/2
    freq_diff = 0.5
    res = math.log2((2*(fmax_nyq/(freq_diff))))
    nfft = int(math.pow(2,res))    
    _df = fmax_nyq/(nfft/2)  
    frqs = np.arange(nsamps)*_df

    # Trim and downsample frequencies.
    keep_ids = _frequency_keep_ids(frqs, settings["fmin"],
                                        settings["fmax"], 1)
    frequencies = frqs[keep_ids]

    # Calculate the spatiospectral correlation matrix
    fdbf_specific = settings.get("fdbf-specific", {})
    weighting = fdbf_specific.get("weighting")
    sscm = _spatiospectral_correlation_matrix(tmatrix,nfft,
                                                    frq_ids=keep_ids,
                                                    weighting=weighting)

    # Weighting
    if weighting == "sqrt":
        offsets_n = offsets.reshape(nrec, 1)
        offsets_h = np.transpose(np.conjugate(offsets_n))
        w = np.dot(offsets_n, offsets_h)
    else:
        w = np.ones((nrec, nrec))

    # Steering
    steering = fdbf_specific.get("steering")
    if steering == "cylindrical":
        def create_steering(kx):
            return np.exp(-1j * np.angle(special.j0(kx) + 1j*special.y0(kx)))
    else:
        def create_steering(kx):
            return np.exp(-1j * kx)

    steer = np.empty((nrec, 1), dtype=complex)
    power = np.empty((len(velocities), len(frequencies)), dtype=complex)
    kx = np.empty_like(offsets)
    for i, f in enumerate(frequencies):
        weighted_sscm = sscm[:, :, i]*w
        for j, v in enumerate(velocities):
            kx[:] = 2*np.pi*f/v * offsets[:]
            steer[:, 0] = create_steering(kx)[:]
            _power = np.dot(np.dot(np.transpose(np.conjugate(steer)),
                                    weighted_sscm), steer)
            power[j, i] = _power

    return (frequencies, power)



