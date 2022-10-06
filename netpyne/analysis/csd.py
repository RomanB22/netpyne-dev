"""
Module with functions to extract and plot CSD info from LFP data

"""

from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals
from __future__ import absolute_import

from future import standard_library
standard_library.install_aliases()

try:
    basestring
except NameError:
    basestring = str

import numpy as np
import scipy

import matplotlib 
from matplotlib import pyplot as plt 
from matplotlib import ticker as ticker
import json
import sys
import os
from collections import OrderedDict  
import warnings 
from scipy.fftpack import hilbert
from scipy.signal import cheb2ord, cheby2, convolve, get_window, iirfilter, remez, decimate
from .filter import lowpass,bandpass
from .utils import exception, _saveFigData 




@exception
def prepareCSD(
    sim=None,
    pop=None,
    timeRange=None,
    dt=None, 
    sampr=None,
    spacing_um=None,
    minf=0.05, 
    maxf=300, 
    vaknin=True,
    norm=True,
    saveData=True,
    getAllData=False,
    **kwargs):
    # electrodes=['avg', 'all'],
    # LFP_input_data=None, 
    # LFP_input_file=None, 



    """
    Function to prepare data for plotting of current source density (CSD) data
    """

    print('Preparing CSD data... ')

    if not sim:
        try:
            from .. import sim
            print('sim import successful')
        except:
            raise Exception('Cannot access sim')


    ## Get LFP data from sim and instantiate as a numpy array 
    simDataCategories = sim.allSimData.keys()
    
    if pop is None:
        if 'LFP' in simDataCategories:
            LFPData = np.array(sim.allSimData['LFP'])
            print('LFPData extracted!')
        else:
            raise Exception('NO LFP DATA!! Need to re-run simulation with cfg.recordLFP enabled')
    else:
        if 'LFPPops' in simDataCategories:
            simLFPPops = sim.allSimData['LFPPops'].keys()
            if pop in simLFPPops:
                print('LFP data available for cell pop ' + str(pop))
                LFPData = sim.allSimData['LFPPops'][pop]
            else:
                # print('No LFP data recorded for ' + str(pop) + ' cell population')
                raise Exception('No LFP data recorded for ' + str(pop) + ' cell population')

    # print(str(type(LFPData)))
    # print(str(LFPData.shape))


    # ## ALTERNATIVE: Get LFP data by doing prepareLFP --> 
    # LFPData_prepareLFP_notArray = sim.analysis.prepareLFP(
    #     sim=sim)
    # LFPData_prepareLFP_notTransposed = np.array(LFPData_prepareLFP_notArray['electrodes']['lfps'])
    # LFPData_prepareLFP_notTruncated = np.transpose(LFPData_prepareLFP_notTransposed)
    # LFPData_prepareLFP = LFPData_prepareLFP_notTruncated[:, 1:]

    # if (LFPData == LFPData_prepareLFP).all():
    #     print('LFPData == LFP_prepareLFP')
    # if np.array_equal(LFPData, LFPData_prepareLFP):
    #     print('double equal check')


    # set time range
    if timeRange is None:
        timeRange = [0, sim.cfg.duration]


    # time step used in simulation recording (in ms)
    if dt is None:
        dt = sim.cfg.recordStep  

    # Sampling rate of data recording during the simulation 
    if sampr is None:
        # divide by 1000.0 to turn denominator from units of ms to s
        sampr = 1.0/(dt/1000.0) # sim.cfg.recordStep == dt


    # Spacing between electrodes (in microns)
    if spacing_um is None:
        spacing_um = sim.cfg.recordLFP[1][1] - sim.cfg.recordLFP[0][1]
    
    # Convert spacing from microns to mm 
    spacing_mm = spacing_um/1000

    print('timeRange, dt, sampr, spacing_um, spacing_mm values all determined')


    ## This retrieves: 
    #   LFPData (as an array)
    #   timeRange --> list [startTime, endTime]
    #   dt --> recording time step (in ms)
    #   sampr --> sampling rate of data recording (in Hz)
    #   spacing_um --> spacing btwn electrodes (in um)


    ####################################

    # Bandpass filter the LFP data with getbandpass() fx defined above
    datband = getbandpass(LFPData,sampr,minf,maxf) 
    print('LFP data bandpassed between ' + str(minf) + ' and ' + str(maxf))

    # Take CSD along smaller dimension
    if datband.shape[0] > datband.shape[1]:
        ax = 1
    else:
        ax = 0
    print('ax = ' + str(ax))

    # Vaknin correction
    if vaknin: 
        datband = Vaknin(datband)

    # norm data
    if norm: 
        removemean(datband,ax=ax)

    # now each column (or row) is an electrode -- take CSD along electrodes
    CSDData = -np.diff(datband, n=2, axis=ax)/spacing_mm**2  
    #### PARTITION BY timeRange!!!!!!! 


    ##### SAVE DATA #######
    # Add CSDData to sim.allSimData for later access
    if saveData:
        if pop is None:
            sim.allSimData['CSD'] = CSDData 
            # sim.allSimData['CSD'] = {}
            # sim.allSimData['CSD']['sampr'] = sampr
            # sim.allSimData['CSD']['spacing_um'] = spacing_um 
            # sim.allSimData['CSD']['CSDData'] = CSDData
        else:
            sim.allSimData['CSDPops'] = {}
            sim.allSimData['CSDPops'][pop] = CSDData 

    # return CSD_data or all data
    if getAllData is True:
        return CSDData, LFPData, sampr, spacing_um, dt
        # if pop is None:
        #     return CSDData, LFPData, sampr, spacing_um, dt
        # else:
        #     return CSDData, LFPData, sampr, spacing_um, dt, pop
    if getAllData is False:
        return CSDData


def getbandpass(
    lfps, 
    sampr, 
    minf=0.05, 
    maxf=300):
    """
    Function to bandpass filter data

    Parameters
    ----------
    lfps : list or array 
        LFP signal data arranged spatially in a column.
        **Default:** *required*

    sampr : float
        The data sampling rate.
        **Default:** *required*

    minf : float
        The high-pass filter frequency (Hz).
        **Default:** ``0.05``

    maxf : float
        The low-pass filter frequency (Hz).
        **Default:** ``300``


    Returns
    -------
    data : array
        The bandpass-filtered data.

    """

    datband = []
    for i in range(len(lfps[0])):datband.append(bandpass(lfps[:,i], minf, maxf, df=sampr, zerophase=True))

    datband = np.array(datband)

    return datband

def Vaknin(x):
    """ 
    Function to perform the Vaknin correction for CSD analysis

    Allows CSD to be performed on all N contacts instead of N-2 contacts (see Vaknin et al (1988) for more details).

    Parameters
    ----------
    x : array 
        Data to be corrected.
        **Default:** *required*


    Returns
    -------
    data : array
        The corrected data.

    """

    # Preallocate array with 2 more rows than input array
    x_new = np.zeros((x.shape[0]+2, x.shape[1]))

    # Duplicate first and last row of x into first and last row of x_new
    x_new[0, :] = x[0, :]
    x_new[-1, :] = x[-1, :]

    # Duplicate all of x into middle rows of x_neww
    x_new[1:-1, :] = x

    return x_new

def removemean(x, ax=1):
    """
    Function to subtract the mean from an array or list

    Parameters
    ----------
    x : array 
        Data to be processed.
        **Default:** *required*

    ax : int
        The axis to remove the mean across.
        **Default:** ``1``


    Returns
    -------
    data : array
        The processed data.

    """
  
    mean = np.mean(x, axis=ax, keepdims=True)
    x -= mean


