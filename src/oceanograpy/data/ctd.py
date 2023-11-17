'''
OCEANOGRAPY.CTD.PY

This should be what a base user interacts with.
'''

import xarray as xr
from oceanograpy.data.ship_ctd_tools import _ctd_tools as tools
import re
from collections import Counter
from oceanograpy.util import time, user_input
import pandas as pd
from oceanograpy.data.nc_format import conventionalize, _standard_attrs, check_conventions
import os

## LOADING AND SAVING DATA

def ctds_from_cnv_dir(
    path: str,
    station_from_filename: bool = False,
    time_warnings: bool = True,
    verbose: bool = True
) -> xr.Dataset:
    """
    Create CTD datasets from CNV files in the specified path.

    Parameters:
    - path (str): Path to the CNV files.
    - station_from_filename (bool): Whether to extract station information from filenames.
    - time_warnings (bool): Enable/disable time-related warnings.
    - verbose: If False, suppress some prints output.
    Returns:
    - D (xarray.Dataset): Joined CTD dataset.
    """
    cnv_files = tools._cnv_files_from_path(path)
    profile_datasets = tools._datasets_from_cnvlist(
        cnv_files, verbose = verbose)
    D = tools.join_cruise(profile_datasets,
        verbose=verbose)
    return D

def ctds_from_cnv_list(
    cnv_list: list,
    station_from_filename: bool = False,
    time_warnings: bool = True,
    verbose: bool = True
) -> xr.Dataset:
    """
    Create CTD datasets from CNV files in the specified path.

    Parameters:
    - path (str): List of CNV file paths.
    - station_from_filename (bool): Whether to extract station information from filenames.
    - time_warnings (bool): Enable/disable time-related warnings.
    - verbose: If False, suppress some prints output.
    Returns:
    - D (xarray.Dataset): Joined CTD dataset.
    """
    profile_datasets = tools._datasets_from_cnvlist(
        cnv_list, verbose = verbose)
    D = tools.join_cruise(profile_datasets,
        verbose=verbose)
    return D



def make_publishing_ready(D, NPI = True, retain_vars = []):
    '''
    Wrapper function:
    Various modifications to the metadata in order to make the dataset
    nicely formatted for publication.
    '''
    D = drop_variables(D, retain_vars = retain_vars)
    D = remove_numbers_in_names(D)
    D = conventionalize.add_standard_var_attrs_ctd(D)
    D = conventionalize.add_standard_glob_attrs_ctd(D, NPI = NPI, 
                                                    override = False)
    D = conventionalize.add_gmdc_keywords_ctd(D)
    D = conventionalize.add_range_attrs_ctd(D)

    D = reorder_attrs(D)

    return D

def quick_metadata_check(D,):



    print('--  QUICK METADATA CHECK --')
    print('NOTE: Not comprehensive! A true check is done on export to netcdf.')

    print('\n# GLOBAL #')

    ### GLOBAL
    attrs_dict_ref = _standard_attrs.global_attrs_ordered.copy()

    attrs_dict_ref.remove('date_created')
    attrs_dict_ref.remove('processing_level')

    for attr in attrs_dict_ref:
        if attr not in D.attrs:
            print(f'- Possibly missing {attr}')

    print('\n# VARIABLE #')

    ### VARIABLE
    attrs_dict_ref_var = _standard_attrs.variable_attrs_necessary

    for varnm in D.variables:
        if 'PRES' in D[varnm].dims:
            _attrs_dict_ref_var = attrs_dict_ref_var.copy()

            if varnm == 'CHLA':
                _attrs_dict_ref_var += [
                    'calibration_formula',
                    'coefficient_A',
                    'coefficient_B',]
            if varnm == 'PRES':
                _attrs_dict_ref_var += [
                    'axis',
                    'positive',]
                _attrs_dict_ref_var.remove('processing_level')
                _attrs_dict_ref_var.remove('QC_indicator')

            any_missing = False
            for var_attr in _attrs_dict_ref_var:
                if var_attr not in D[varnm].attrs:
                    print(f'- {varnm}: Possibly missing {var_attr}')
                    any_missing = True
            if not any_missing:
                    print(f'- {varnm}: OK')

    other_dict = {
        'LATITUDE':['units', 'standard_name', 'long_name', 'axis'],
        'LONGITUDE':['units', 'standard_name', 'long_name', 'axis'],
        'STATION':['cf_role', 'long_name'],
        'CRUISE':['long_name'],
        }
    for varnm, _attrs_dict_ref_var in other_dict.items():
        if varnm in D:
            any_missing = False
            for var_attr in _attrs_dict_ref_var:
                if var_attr not in D[varnm].attrs:
                    print(f'- {varnm}: Possibly missing {var_attr}')
                    any_missing = True
            if not any_missing:
                    print(f'- {varnm}: OK')




def to_netcdf(D, path, file_name = None, convention_check = False, add_to_history = True):
    '''
    Export to netCDF
    using the 'id' attribute as file name if file_name not specified
    if that dossn't exist, use 'CTD_DATASET_NO_NAME'
    
    '''
    D = add_now_as_date_created(D)
    D = reorder_attrs(D)

    if file_name == None:
        try:
            file_name = D.id
        except:
            file_name = 'CTD_DATASET_NO_NAME'

    file_path = f'{path}{file_name}.nc'

    if add_to_history:
        now_time = pd.Timestamp.now().strftime('%Y-%m-%d')
        D.attrs['history'] = D.history + f'\n{now_time}: Creation of this netcdf file.'
        print(f'Updated history attribute. Current content:\n---')
        print(D.history)
        print('---')
              

    D.to_netcdf(file_path)

    print(f'Exported file {file_name}.nc to {path}.')

    if convention_check:
        print('Running convention checker:')
        check_conventions.check_file(file_path)


## APPLYING CORRECTIONS ETC

import xarray as xr
from typing import Optional

def calibrate_chl(
    D: xr.Dataset,
    A: float,
    B: float,
    chl_name_in: Optional[str] = 'CHLA1_instr',
    chl_name_out: Optional[str] = None,
    verbose: Optional[bool] = True,
    remove_uncal: Optional[bool] = False
) -> xr.Dataset:
    """
    Apply a calibration to chlorophyll based on a fit based on water samples.

    CHLA -> A * CHLA_instr + B

    Where CHLA_instr is the name of the variable containing uncalibrated 
    chlorophyll from the instrument.

    Append suitable metadata.

    Parameters
    ----------
    D : xr.Dataset
        Dataset containing A, B: Linear coefficients based on fitting to chl samples.
    A : float
        Linear coefficient for calibration.
    B : float
        Linear coefficient for calibration.
    chl_name_in : str, optional
        Name of the variable containing uncalibrated chlorophyll from the instrument.
        Default is 'CHLA1_instr'.
    chl_name_out : str, optional
        Name of the calibrated chlorophyll variable. If not provided, it is derived from
        chl_name_in. Default is None.
    verbose : bool, optional
        If True, print messages about the calibration process. Default is True.
    remove_uncal : bool, optional
        If True, remove the uncalibrated chlorophyll from the dataset. Default is False.

    Returns
    -------
    xr.Dataset
        Updated dataset with calibrated chlorophyll variable.
    """
    # Determine the output variable name for calibrated chlorophyll
    # If we don't specify a variable name for the calibrated chlorophyll, the
    # default behaviour is to 
    # a) Use the uncalibrated chl name without the '_instr' suffix (if it 
    #    has one), or 
    # b) Use the uncalibrated chl name with the suffix '_cal' 
    if not chl_name_out:
        chl_name_out = (
            chl_name_in.replace('_instr', '') if '_instr' in chl_name_in
            else f'{chl_name_in}_cal'
        )

    # Create a new variable with the coefficients applied
    D[chl_name_out] = A * D[chl_name_in] + B
    D[chl_name_out].attrs = {key: item for key, item in D[chl_name_in].attrs.items()}

    # Add suitable attributes
    new_attrs = {
        'long_name': ('Chlorophyll-A concentration calibrated against'
                      ' water sample measurements'),
        'calibration_formula': 'chla_calibrated = A * chla_from_ctd + B',
        'coefficient_A': A,
        'coefficient_B': B,
    }

    for key, item in new_attrs.items():
        D[chl_name_out].attrs[key] = item

    # Remove the uncalibrated chla 
    if remove_uncal:
        remove_str = f' Removed uncalibrated Chl-A ("{chl_name_in}") from the dataset.'
        D = D.drop(chl_name_in)
    else:
        remove_str = ''

    # Print
    if verbose:
        print(f'Added calibrated Chl-A ("{chl_name_out}").{remove_str}')

    return D



def drop_variables(D, retain_vars = ['TEMP1', 'CNDC1', 'PSAL1', 'CHLA1'], 
                   drop_vars = None, 
                    ):
        '''
        Drop measurement variables from the dataset.

        Will retain variables that don't have a PRES dimension, such as
        LATITUDE, TIME, STATION.

        Provide *either* strip_vars or retain_vars (not both). retain_vars
        is ignored if drop_vars is specified.
        
        Parameters:

        D: xarray dataset 
        retain_vars: (list or bool) Variables to retain (others will be retained) 
        drop_vars: (list or bool) Variables to drop (others will be retained) 

        '''

        if drop_vars:
            D = D.drop(drop_vars)
            dropped = drop_vars
        else:
            all_vars = [varnm for varnm in D.data_vars]
            dropped = []
            for varnm in all_vars:
                if varnm not in retain_vars and 'PRES' in D[varnm].dims:
                    D = D.drop(varnm)
                    dropped += [varnm]

        print(f'Dropped these variables from the Dataset: {dropped}.')

        return D



## SMALL FUNCTIONS FOR MODIFYING METADATA ETC

def set_glob_attr(D, attr):
    '''
    Set global attributes for a  dataset or data frame.

    Using interactive widgets. 
    '''

    option_dict = _standard_attrs.global_attrs_options
    if attr in option_dict:
        D = user_input.set_attr_pulldown(D, attr, 
                    _standard_attrs.global_attrs_options[attr])
    else:
        # Make a larger box for (usually) long attributes
        if attr in ['summary', 'comment', 'acknowledgment']:
            rows = 10
        else:
            rows = 1
        D = user_input.set_attr_textbox(D, attr, rows)

    return D



def set_var_attr(D, varname, attr):
    '''
    Set variable attributes for a  dataset or data frame.

    Using interactive widgets. 
    '''

    option_dict = _standard_attrs.global_attrs_options
    if attr in option_dict:
        D = user_input.set_var_attr_pulldown(D, varname, attr, 
                    _standard_attrs.global_attrs_options[attr])
    else:
        # Make a larger box for (usually) long attributes
        if attr in ['summary', 'comment', 'acknowledgment']:
            rows = 10
        else:
            rows = 1
        D = user_input.set_var_attr_textbox(D, varname, attr, rows)

    return D


def remove_numbers_in_names(D):
    '''
    Remove numbers from variable names like "TEMP1", "PSAL2".

    If more than one exists (e.g. "TEMP1", "TEMP2") -> don't change anything.
    '''
    # Get variable names
    all_varnms = [varnm for varnm in D.data_vars]

    # Get number-stripped names 
    varnms_stripped = [re.sub(r'\d', '', varnm) for varnm in all_varnms]

    # Identify duplicates 
    counter = Counter(varnms_stripped)
    duplicates = [item for item, count in counter.items() if count > 1]

    # Strip names
    for varnm in all_varnms:
        if varnm not in duplicates:
            varnm_stripped = re.sub(r'\d', '', varnm)
            D = D.rename_vars({varnm:varnm_stripped})

    return D

def add_now_as_date_created(D):
    '''
    Add a global attribute "date_created" with todays date.
    '''
    now_time = pd.Timestamp.now()
    now_str = time.datetime_to_ISO8601(now_time)

    D.attrs['date_created'] = now_str

    return D


def reorder_attrs(D):
    """
    Reorder global and variable attributes of a dataset based on the 
    specified order in _standard_attrs.

    Parameters:
        ds (xarray.Dataset): The dataset containing global attributes.
        ordered_list (list): The desired order of global attributes.

    Returns:
        xarray.Dataset: The dataset with reordered global attributes.
    """
    ### GLOBAL
    reordered_list = _reorder_list(D.attrs, 
                                  _standard_attrs.global_attrs_ordered)
    attrs_dict = D.attrs
    D.attrs = {}
    for attr_name in reordered_list:
        D.attrs[attr_name] = attrs_dict[attr_name]

    ### VARIABLE
    for varnm in D.data_vars:
        reordered_list_var = _reorder_list(D[varnm].attrs, 
                      _standard_attrs.variable_attrs_ordered)
        var_attrs_dict = D[varnm].attrs
        D[varnm].attrs = {}
        for attr_name in reordered_list_var:
            D[varnm].attrs[attr_name] = var_attrs_dict[attr_name]
    return D



def _reorder_list(input_list, ordered_list):
    '''
    reorder a list input_list according to the order specified in ordered_list
    '''
    # Create a set of existing attributes for quick lookup
    existing_attributes = set(input_list)

    # Extract ordered attributes that exist in the dataset
    ordered_attributes = [attr for attr in ordered_list if attr in existing_attributes]

    # Add any remaining attributes that are not in the ordered list
    remaining_attributes = [attr for attr in input_list if attr not in ordered_attributes]

    # Concatenate the ordered and remaining attributes
    reordered_attributes = ordered_attributes + remaining_attributes

    return reordered_attributes
