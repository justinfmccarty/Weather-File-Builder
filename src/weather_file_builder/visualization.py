"""
TMY visualization tools.

Functions for creating plots that show how TMY files were constructed
from individual years of weather data.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyArrowPatch
from datetime import datetime
from typing import Dict, Optional
import warnings


def create_tmy_plot(
    multi_year_data: pd.DataFrame,
    tmy_data: pd.DataFrame,
    selected_years: Dict[int, int],
    latitude: float = None,
    longitude: float = None,
    variable: str = 'Temperature',
    output_path: Optional[str] = None,
    figsize: Optional[tuple] = None,
    dpi: int = 150
) -> plt.Figure:
    """
    Create a visualization showing how TMY was constructed from individual years.
    
    Creates a multi-panel plot with:
    - One panel per year that was selected for at least one month
    - Highlighted months that were selected for the TMY
    - Arrows connecting selected months to final TMY
    - Bottom panel showing the final constructed TMY
    
    Note: Only years that contributed to the TMY are shown (not all years from
    the source data). This creates a cleaner, more focused visualization.
    
    Parameters
    ----------
    multi_year_data : pd.DataFrame
        Multi-year source data with 'Year', 'Month', 'Day', 'Hour', and variable columns.
        Only years that were selected for the TMY will be plotted.
    tmy_data : pd.DataFrame
        Constructed TMY data
    selected_years : dict
        Dictionary mapping month (1-12) to selected year
    latitude : float, optional
        Location latitude for plot title. If None, will attempt to extract from
        multi_year_data['Latitude'] column.
    longitude : float, optional
        Location longitude for plot title. If None, will attempt to extract from
        multi_year_data['Longitude'] column.
    variable : str, default 'Temperature'
        Variable to plot
    output_path : str, optional
        Path to save figure (if None, figure is not saved)
    figsize : tuple, optional
        Figure size (width, height). If None, auto-calculated based on number of selected years
    dpi : int, default 150
        Resolution for saved figure
    
    Returns
    -------
    matplotlib.figure.Figure
        The created figure
    
    Examples
    --------
    >>> df = download_multi_year(40.7, -74.0, range(2010, 2020))
    >>> tmy_data, selected_years = create_tmy(df)
    >>> fig = create_tmy_plot(df, tmy_data, selected_years, 40.7, -74.0)
    >>> fig.savefig('tmy_construction.png')
    """
    # Validate inputs
    if 'Year' not in multi_year_data.columns or 'Month' not in multi_year_data.columns:
        raise ValueError("multi_year_data must have 'Year' and 'Month' columns")
    
    if variable not in multi_year_data.columns:
        raise ValueError(f"Variable '{variable}' not found in data")
    
    # Extract latitude/longitude from dataframe if not provided
    if latitude is None and 'Latitude' in multi_year_data.columns:
        latitude = multi_year_data['Latitude'].iloc[0]
        if pd.notna(latitude):
            print(f"Using latitude from data: {latitude:.4f}")
        else:
            latitude = 0.0  # Fallback
    elif latitude is None:
        latitude = 0.0  # Fallback
    
    if longitude is None and 'Longitude' in multi_year_data.columns:
        longitude = multi_year_data['Longitude'].iloc[0]
        if pd.notna(longitude):
            print(f"Using longitude from data: {longitude:.4f}")
        else:
            longitude = 0.0  # Fallback
    elif longitude is None:
        longitude = 0.0  # Fallback
    
    # Get only the years that were selected for TMY (not all years)
    years_used = sorted(set(selected_years.values()))
    n_years = len(years_used)
    
    # Filter data to only include years used in TMY
    multi_year_data = multi_year_data[multi_year_data['Year'].isin(years_used)].copy()
    
    print(f"Creating TMY visualization with {n_years} selected years: {years_used}")
    
    # Auto-calculate figure size if not provided
    if figsize is None:
        figsize = (9, n_years + 1)
    
    # Create figure with subplots
    fig, axs = plt.subplots(ncols=1, nrows=n_years + 1, figsize=figsize)
    
    # Ensure axs is always a list
    if not isinstance(axs, (list, np.ndarray)):
        axs = [axs]
    
    # Get temperature range for consistent y-axis
    ymin = multi_year_data[variable].min()
    ymax = multi_year_data[variable].max()
    
    # Use a common plot year for x-axis alignment
    plot_year = datetime.now().year
    
    # Remove leap days from both datasets
    mask = (multi_year_data['Month'] == 2) & (multi_year_data['Day'] == 29)
    multi_year_data = multi_year_data[~mask].reset_index(drop=True)
    mask = (tmy_data['Month'] == 2) & (tmy_data['Day'] == 29)
    tmy_data = tmy_data[~mask].reset_index(drop=True)

    # Prepare data with common year for plotting
    data_indexed = multi_year_data.copy()
    data_indexed['PlotYear'] = plot_year
    
    # Create datetime index for plotting
    # try:
    #     data_indexed['PlotDate'] = pd.to_datetime(
    #         data_indexed[['PlotYear', 'Month', 'Day', 'Hour']].rename(
    #             columns={'PlotYear': 'year', 'Month': 'month', 'Day': 'day', 'Hour': 'hour'}
    #         )
    #     )
    # except:
    #     # Fallback if Day/Hour columns don't exist
    #     data_indexed['PlotDate'] = pd.to_datetime(
    #         data_indexed[['PlotYear', 'Month']].assign(day=1).rename(
    #             columns={'PlotYear': 'year', 'Month': 'month'}
    #         )
    #     )
    
    data_indexed['PlotDate'] = pd.to_datetime({
        "year": 2025,
        "month": data_indexed["Month"],
        "day": data_indexed["Day"],
        "hour": data_indexed["Hour"],
        "minute": data_indexed["Minute"],
        "second": 0
    })
    
    # Prepare TMY data
    tmy_indexed = tmy_data.copy()
    tmy_indexed['PlotYear'] = plot_year
    
    # try:
    #     tmy_indexed['PlotDate'] = pd.to_datetime(
    #         tmy_indexed[['PlotYear', 'Month', 'Day', 'Hour']].rename(
    #             columns={'PlotYear': 'year', 'Month': 'month', 'Day': 'day', 'Hour': 'hour'}
    #         )
    #     )
    # except:
        # tmy_indexed['datetime'] = pd.to_datetime(
        #     tmy_indexed[['PlotYear' ,'Month', 'Day', 'Hour', 'Minute']].assign(second=0).rename(
        #         columns={'PlotYear': 'year', 'Month': 'month', 'Day': 'day', 'Hour': 'hour'}
        #     )
        # )
    
    tmy_indexed['PlotDate'] = pd.to_datetime({
        "year": 2025,
        "month": tmy_indexed["Month"],
        "day": tmy_indexed["Day"],
        "hour": tmy_indexed["Hour"],
        "minute": tmy_indexed["Minute"],
        "second": 0
    })
    
    
    # Line width settings
    primary_lw = 0.75
    dashed_lw = 0.25
    sub_lw = 0.35
    
    # Calculate monthly boundaries for grid lines
    month_boundaries = []
    for month in range(1, 13):
        month_boundaries.append(datetime(plot_year, month, 1))
    
    # Store arrow information for later drawing
    arrow_info = []
    
    print(f"Creating TMY visualization with {n_years} years...")
    
    for n, ax in enumerate(axs):
        if n == n_years:
            # Last panel: Constructed TMY
            # Plot all individual years in grey
            for year in years_used:
                year_data = data_indexed[data_indexed['Year'] == year]
                if not year_data.empty:
                    # Plot all hourly data (no resampling)
                    ax.plot(year_data['PlotDate'], year_data[variable], 
                           lw=sub_lw, c="grey", alpha=0.5)
            
            # Plot TMY in red
            if not tmy_indexed.empty:
                ax.plot(tmy_indexed['PlotDate'], tmy_indexed[variable], 
                       lw=primary_lw, c="red")
        
        else:
            # Individual year panels
            year = years_used[n]
            
            # Plot other years in grey
            for other_year in [y for y in years_used if y != year]:
                other_data = data_indexed[data_indexed['Year'] == other_year]
                
                if not other_data.empty:
                    # Plot all hourly data (no resampling)
                    ax.plot(other_data['PlotDate'], other_data[variable], 
                           lw=sub_lw, c="grey", alpha=0.5)
            
            # Plot current year in red
            year_data = data_indexed[data_indexed['Year'] == year]
            if not year_data.empty:
                ax.plot(year_data['PlotDate'], year_data[variable], 
                       lw=primary_lw, c="red")
            
            # Highlight selected months and prepare arrows
            selected_months = [month for month, sel_year in selected_years.items() 
                             if sel_year == year]
            for month in selected_months:
                # Highlight month span
                month_start = datetime(plot_year, month, 1)
                if month == 12:
                    month_end = datetime(plot_year + 1, 1, 1)
                else:
                    month_end = datetime(plot_year, month + 1, 1)
                
                ax.axvspan(month_start, month_end, zorder=3,
                          facecolor="red", alpha=0.2)
                
                # Store arrow information
                month_center = month_start + (month_end - month_start) / 2
                arrow_x = mdates.date2num(month_center)
                arrow_y = (ymin + ymax) / 2
                
                arrow_info.append({
                    'source_ax': ax,
                    'source_x': arrow_x,
                    'source_y': arrow_y,
                    'target_ax': axs[-1],
                    'target_x': arrow_x,
                    'target_y': ymax
                })
        
        # Add monthly grid lines
        ax.vlines(month_boundaries, ymin, ymax,
                 lw=dashed_lw, colors="black", linestyle="dashed")
        
        # Remove axis labels and ticks for cleaner look
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        
        # Set limits (extend to Jan 1 of next year to show all of December)
        ax.set_xlim([datetime(plot_year, 1, 1), datetime(plot_year + 1, 1, 1)])
        ax.set_ylim([ymin, ymax])
        
        # Add subplot titles
        title_fontsize = 8
        if n == n_years:
            ax.text(0, -0.05, "Constructed Weather Data", 
                   transform=ax.transAxes, fontsize=title_fontsize, 
                   color='black', ha='left', va='top')
        else:
            ax.text(0, 1.02, str(year), transform=ax.transAxes,
                   fontsize=title_fontsize, color='black', ha='left', va='bottom')
    
    # Adjust layout before adding arrows
    plt.tight_layout()
    
    # Add arrows connecting selected months to TMY
    for arrow_data in arrow_info:
        try:
            # Convert data coordinates to display coordinates
            source_disp = arrow_data['source_ax'].transData.transform(
                (arrow_data['source_x'], arrow_data['source_y'])
            )
            target_disp = arrow_data['target_ax'].transData.transform(
                (arrow_data['target_x'], arrow_data['target_y'])
            )
            
            # Convert to figure coordinates
            source_fig = fig.transFigure.inverted().transform(source_disp)
            target_fig = fig.transFigure.inverted().transform(target_disp)
            
            # Create arrow
            arrow = FancyArrowPatch(
                source_fig, target_fig,
                arrowstyle='->, head_length=4, head_width=5',
                lw=primary_lw,
                color='k',
                alpha=0.5,
                transform=fig.transFigure,
                zorder=1000
            )
            
            fig.patches.append(arrow)
        except Exception as e:
            warnings.warn(f"Could not create arrow: {e}")
            continue
    
    # Set figure title
    fig.suptitle(f'Typical {variable}: {round(latitude, 2)}, {round(longitude, 2)} - Year Range: {multi_year_data["Year"].min()}-{multi_year_data["Year"].max()}',
                fontsize=10, x=0.018, y=0.99, ha='left', va='bottom')
    
    # Save figure if path provided
    if output_path:
        fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
        print(f"Plot saved to: {output_path}")
    
    print("TMY visualization complete!")
    
    return fig
