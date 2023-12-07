'''
Functions for visualizing ctd data.

These are meant to be run in a Jupyter Lab notebook using the 
%matplotlib widget backend.

These functions are rather complex and clunky because they are tuned for the visual 
input and menu functionality we want for the specific application. I am not too worried
about that.
'''

import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from oceanograpy.util import time
from oceanograpy.maps import quickmap
from matplotlib.ticker import MaxNLocator
import cmocean
import numpy as np

def inspect_profiles(d):
    """
    Function to interactively inspect profiles in an xarray dataset.

    Parameters:
    - d (xr.Dataset): The xarray dataset containing variables 'PRES', 'STATION', and other profile variables.

    """

    # Function to create a profile plot
    def plot_profile(station_index, variable):
        fig, ax = plt.subplots()

        # Plot all profiles in black in the background
        for nn, station in enumerate(d['STATION']):
            if nn != station_index:  # Skip the selected profile
                profile =  d[variable].where(d['STATION'] == station, drop=True).squeeze()
                ax.plot(profile, d['PRES'], color='tab:blue', lw=0.5, alpha=0.4)

        # Plot the selected profile in color
        profile = d[variable].isel(TIME=station_index)

        ax.plot(profile, d['PRES'], alpha=0.8, lw=0.7, color='k')
        ax.plot(profile, d['PRES'], '.', ms=2, alpha=1, color='tab:orange')

        station_time_string = time.convert_timenum_to_datetime(profile.TIME, d.TIME.units)
        ax.set_title(f'Station: {d["STATION"].values[station_index]}, {station_time_string}')
        ax.set_xlabel(f'{variable} [{d[variable].units}]')
        ax.set_ylabel('PRES')
        ax.invert_yaxis()
        ax.grid()
        fig.canvas.header_visible = False  # Hide the figure header
        plt.tight_layout()

        plt.show()

    # Get the descriptions for the slider
    station_descriptions = [str(station) for station in d['STATION'].values]

    # Create the slider for selecting a station
    station_index_slider = widgets.IntSlider(
        min=0, max=len(d['STATION']) - 1, step=1, value=0, description='Profile #:',
        continuous_update=False,
        style={'description_width': 'initial'},
        layout=widgets.Layout(width='600px')  # Set the width of the slider
    )

    profile_vars = _get_profile_variables(d)

    # Create the dropdown for selecting a variable
    variable_dropdown = widgets.Dropdown(
        options=profile_vars,
        value=profile_vars[0],
        description='Variable:'
    )

    # Create the dropdown for selecting a station
    station_dropdown = widgets.Dropdown(
        options=station_descriptions,
        value=station_descriptions[0],
        description='Station:'
    )

    # Update slider value when dropdown changes
    def update_slider_from_dropdown(change):
        station_index = station_descriptions.index(change.new)
        station_index_slider.value = station_index

    # Update dropdown value when slider changes
    def update_dropdown_from_slider(change):
        station_description = str(d['STATION'].values[change.new])
        station_dropdown.value = station_description

    # Link slider and dropdown
    station_dropdown.observe(update_slider_from_dropdown, names='value')
    station_index_slider.observe(update_dropdown_from_slider, names='value')

    # Use interactive_output to create interactive controls
    output = widgets.interactive_output(
        plot_profile, {'station_index': station_index_slider, 'variable': variable_dropdown}
    )

    # Display the widgets in a vertically stacked layout
    display(widgets.VBox([
        widgets.HBox([station_index_slider]),
        widgets.HBox([variable_dropdown, station_dropdown]),
        output
    ]))



def map(D, height=1000, width=1000, return_fig_ax=False, coast_resolution='50m', figsize=None):
    '''
    Quick map of cruise
    '''
    # These would maybe be useful for auto-scaling of the map..
    lat_span = float(D.LATITUDE.max() - D.LATITUDE.min())
    lon_span = float(D.LONGITUDE.max() - D.LONGITUDE.min())
    lat_ctr = float(0.5 * (D.LATITUDE.max() + D.LATITUDE.min()))
    lon_ctr = float(0.5 * (D.LONGITUDE.max() + D.LONGITUDE.min()))

    fig, ax = quickmap.quick_map_stere(lon_ctr, lat_ctr, height=height,
                                       width=width,
                                       coast_resolution=coast_resolution,)

    fig.canvas.header_visible = False  # Hide the figure header
    
    ax.plot(D.LONGITUDE, D.LATITUDE, '-k', transform=ccrs.PlateCarree(), alpha=0.5)
    ax.plot(D.LONGITUDE, D.LATITUDE, 'or', transform=ccrs.PlateCarree())

    plt.tight_layout()
    
    if figsize:
        fig.set_size_inches(figsize)
    else:
        figsize = fig.get_size_inches()

    # Create a button to minimize the plot
    minimize_button = widgets.Button(description="Minimize")

    def minimize_plot(_):
        # Resize the figure to 2x
        fig.set_size_inches(0.1, 0.1)
        fig.canvas.draw()

    minimize_button.on_click(minimize_plot)

    # Create a button to restore full size
    org_size_button = widgets.Button(description="Original Size")

    def org_size_plot(_):
        # Resize the figure to its original size
        fig.set_size_inches(figsize)
        fig.canvas.draw()

    # Create a button to restore full size
    full_size_button = widgets.Button(description="Larger")

    def full_size_plot(_):
        # Resize the figure to its original size
        fig.set_size_inches(fig.get_size_inches()*2)
        fig.canvas.draw()

    minimize_button.on_click(minimize_plot)
    org_size_button.on_click(org_size_plot)
    full_size_button.on_click(full_size_plot)

    # Create a static text widget
    static_text = widgets.HTML(value='<p>Use the menu on the left of the figure to zoom/move around/save</p>')

    # Display both buttons and text with decreased vertical spacing
    display(
        widgets.HBox([minimize_button, org_size_button, full_size_button, static_text], layout=widgets.Layout(margin='0 0 5px 0', align_items='center')))
    
    if return_fig_ax:
        return fig, ax




def ctd_contours(D):
    """
    Function to create interactive contour plots based on an xarray dataset.

    Parameters:
    - D (xr.Dataset): The xarray dataset containing profile variables and coordinates.

    """

    # Function to update plots based on variable, xvar, and max depth selection
    def update_plots(variable1, variable2, xvar, max_depth):
        fig, ax = plt.subplots(2, 1, sharex=True, sharey=True)
        fig.canvas.header_visible = False  # Hide the figure header

        for axn, varnm in zip(ax, [variable1, variable2]):
            colormap = _cmap_picker(varnm)
            plt.xticks(rotation=0)
            
            if xvar == 'TIME':
                x_data = result_timestamp = time.datenum_to_timestamp(
                    D.TIME, D.TIME.units)
                plt.xticks(rotation=90)
                x_label = 'Time'
            elif xvar == 'LONGITUDE':
                x_data = D[xvar]
                x_label = 'Longitude'
            elif xvar == 'LATITUDE':
                x_data = D[xvar]
                x_label = 'Latitude'
            elif xvar == 'Profile #':
                x_data = np.arange(D.dims['TIME'])
                x_label = 'Profile #'
            else:
                raise ValueError(f"Invalid value for xvar: {xvar}")

            C = axn.contourf(x_data, D.PRES, D[varnm].T, cmap=colormap, levels = 30)
            cb = plt.colorbar(C, ax=axn, label=D[varnm].units)
            
            # Set colorbar ticks using MaxNLocator
            cb.locator = MaxNLocator(nbins=6)  # Adjust the number of ticks as needed
            cb.update_ticks()

            axn.plot(x_data, np.zeros(D.dims['TIME']), '|k', clip_on = False, zorder = 0)

            axn.set_title(varnm)

            conts = axn.contour(x_data, D.PRES, D[varnm].T, colors = 'k', 
                                linewidths = 0.8, alpha = 0.2, levels = cb.get_ticks())

            axn.set_facecolor('lightgray')
            axn.set_ylabel('PRES [dbar]')

        ax[1].set_xlabel(x_label)
        ax[0].set_ylim(max_depth, 0)
        plt.tight_layout()

        plt.show()

    # Get the list of available variables
    available_variables = _get_profile_variables(D)

    # Create dropdowns for variable selection
    variable_dropdown1 = widgets.Dropdown(options=available_variables, 
                                          value=available_variables[0], description='Variable 1:')
    variable_dropdown2 = widgets.Dropdown(options=available_variables, 
                                          value=available_variables[1], description='Variable 2:')

    # Create dropdown for x-variable selection
    xvar_dropdown = widgets.Dropdown(options=['TIME', 'LONGITUDE', 'LATITUDE', 'Profile #'], 
                                     value='Profile #', description='x axis:')

    # Create slider for max depth selection
    max_depth_slider = widgets.IntSlider(min=1, max=D.PRES[-1].values, step=1, 
                                         value=D.PRES[-1].values, description='Max depth [m]:')

    # Use interactive to update plots based on variable, xvar, and max depth selection
    out = widgets.interactive_output(update_plots, 
                                     {'variable1': variable_dropdown1, 
                                      'variable2': variable_dropdown2, 
                                      'xvar': xvar_dropdown, 
                                      'max_depth': max_depth_slider})
    display(widgets.VBox([widgets.HBox([variable_dropdown1, variable_dropdown2]), 
                          xvar_dropdown, max_depth_slider, out]))



def _cmap_picker(varnm):
    '''
    Choose the appropriate colormap fir different variables.
    '''
    cmap_name = 'amp'
    if 'TEMP' in varnm:
        cmap_name = 'thermal'
    elif 'PSAL' in varnm:
        cmap_name = 'haline'
    elif 'CHLA' in varnm:
        cmap_name = 'algae'
    elif 'SIGTH' in varnm:
        cmap_name = 'deep'
    cmap = getattr(cmocean.cm, cmap_name)

    return cmap


# Get the profile variables
def _get_profile_variables(d):
    '''
    Return a list of profile variables (i.e. variables with TIME, PRES dimensions)
    '''
    profile_variables = [varnm for varnm in d.data_vars if 'PRES' in d[varnm].dims 
                            and 'TIME' in d[varnm].dims]
    return profile_variables