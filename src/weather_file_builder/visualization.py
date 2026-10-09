"""
TMY visualisation tools.

Functions for creating plots that show how TMY files were constructed
from individual years of weather data.
"""

import logging
import warnings
from datetime import datetime
from typing import Dict, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch

logger = logging.getLogger(__name__)


def create_tmy_plot(
    multi_year_data: pd.DataFrame,
    tmy_data: pd.DataFrame,
    selected_years: Dict[int, int],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    variable: str = "Temperature",
    output_path: Optional[str] = None,
    figsize: Optional[tuple] = None,
    dpi: int = 150,
) -> plt.Figure:
    """Create a visualisation showing how TMY was constructed from individual years.

    Creates a multi-panel plot with:
    - One panel per year that was selected for at least one month
    - Highlighted months that were selected for the TMY
    - Arrows connecting selected months to final TMY
    - Bottom panel showing the final constructed TMY

    Only years that contributed to the TMY are shown (not all years from
    the source data).

    Parameters
    ----------
    multi_year_data : pd.DataFrame
        Multi-year source data with ``'Year'``, ``'Month'``, ``'Day'``,
        ``'Hour'``, and variable columns.
    tmy_data : pd.DataFrame
        Constructed TMY data.
    selected_years : dict
        Dictionary mapping month (1-12) to selected year.
    latitude : float, optional
        Location latitude for plot title.
    longitude : float, optional
        Location longitude for plot title.
    variable : str, default ``'Temperature'``
        Variable to plot.
    output_path : str, optional
        Path to save figure.
    figsize : tuple, optional
        Figure size ``(width, height)``.
    dpi : int, default 150
        Resolution for saved figure.

    Returns
    -------
    matplotlib.figure.Figure
        The created figure.
    """
    if "Year" not in multi_year_data.columns or "Month" not in multi_year_data.columns:
        raise ValueError("multi_year_data must have 'Year' and 'Month' columns")

    if variable not in multi_year_data.columns:
        raise ValueError(f"Variable '{variable}' not found in data")

    if latitude is None and "Latitude" in multi_year_data.columns:
        latitude = multi_year_data["Latitude"].iloc[0]
        if pd.isna(latitude):
            latitude = 0.0
    elif latitude is None:
        latitude = 0.0

    if longitude is None and "Longitude" in multi_year_data.columns:
        longitude = multi_year_data["Longitude"].iloc[0]
        if pd.isna(longitude):
            longitude = 0.0
    elif longitude is None:
        longitude = 0.0

    years_used = sorted(set(selected_years.values()))
    n_years = len(years_used)

    multi_year_data = multi_year_data[multi_year_data["Year"].isin(years_used)].copy()

    logger.info(
        "Creating TMY visualisation with %d selected years: %s", n_years, years_used,
    )

    if figsize is None:
        figsize = (9, n_years + 1)

    fig, axs = plt.subplots(ncols=1, nrows=n_years + 1, figsize=figsize)

    if not isinstance(axs, (list, np.ndarray)):
        axs = [axs]

    ymin = multi_year_data[variable].min()
    ymax = multi_year_data[variable].max()

    plot_year = datetime.now().year

    # Remove leap days
    mask = (multi_year_data["Month"] == 2) & (multi_year_data["Day"] == 29)
    multi_year_data = multi_year_data[~mask].reset_index(drop=True)
    mask = (tmy_data["Month"] == 2) & (tmy_data["Day"] == 29)
    tmy_data = tmy_data[~mask].reset_index(drop=True)

    data_indexed = multi_year_data.copy()
    data_indexed["PlotDate"] = pd.to_datetime({
        "year": plot_year,
        "month": data_indexed["Month"],
        "day": data_indexed["Day"],
        "hour": data_indexed["Hour"],
        "minute": data_indexed["Minute"],
        "second": 0,
    })

    tmy_indexed = tmy_data.copy()
    tmy_indexed["PlotDate"] = pd.to_datetime({
        "year": plot_year,
        "month": tmy_indexed["Month"],
        "day": tmy_indexed["Day"],
        "hour": tmy_indexed["Hour"],
        "minute": tmy_indexed["Minute"],
        "second": 0,
    })

    primary_lw = 0.75
    dashed_lw = 0.25
    sub_lw = 0.35

    month_boundaries = [datetime(plot_year, month, 1) for month in range(1, 13)]

    arrow_info = []

    for n, ax in enumerate(axs):
        if n == n_years:
            for year in years_used:
                year_data = data_indexed[data_indexed["Year"] == year]
                if not year_data.empty:
                    ax.plot(
                        year_data["PlotDate"], year_data[variable],
                        lw=sub_lw, c="grey", alpha=0.5,
                    )

            if not tmy_indexed.empty:
                ax.plot(
                    tmy_indexed["PlotDate"], tmy_indexed[variable],
                    lw=primary_lw, c="red",
                )

        else:
            year = years_used[n]

            for other_year in [y for y in years_used if y != year]:
                other_data = data_indexed[data_indexed["Year"] == other_year]
                if not other_data.empty:
                    ax.plot(
                        other_data["PlotDate"], other_data[variable],
                        lw=sub_lw, c="grey", alpha=0.5,
                    )

            year_data = data_indexed[data_indexed["Year"] == year]
            if not year_data.empty:
                ax.plot(
                    year_data["PlotDate"], year_data[variable],
                    lw=primary_lw, c="red",
                )

            selected_months = [
                month for month, sel_year in selected_years.items() if sel_year == year
            ]
            for month in selected_months:
                month_start = datetime(plot_year, month, 1)
                if month == 12:
                    month_end = datetime(plot_year + 1, 1, 1)
                else:
                    month_end = datetime(plot_year, month + 1, 1)

                ax.axvspan(
                    month_start, month_end, zorder=3, facecolor="red", alpha=0.2,
                )

                month_center = month_start + (month_end - month_start) / 2
                arrow_x = mdates.date2num(month_center)
                arrow_y = (ymin + ymax) / 2

                arrow_info.append({
                    "source_ax": ax,
                    "source_x": arrow_x,
                    "source_y": arrow_y,
                    "target_ax": axs[-1],
                    "target_x": arrow_x,
                    "target_y": ymax,
                })

        ax.vlines(
            month_boundaries, ymin, ymax,
            lw=dashed_lw, colors="black", linestyle="dashed",
        )

        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])

        ax.set_xlim([datetime(plot_year, 1, 1), datetime(plot_year + 1, 1, 1)])
        ax.set_ylim([ymin, ymax])

        title_fontsize = 8
        if n == n_years:
            ax.text(
                0, -0.05, "Constructed Weather Data",
                transform=ax.transAxes, fontsize=title_fontsize,
                color="black", ha="left", va="top",
            )
        else:
            ax.text(
                0, 1.02, str(year),
                transform=ax.transAxes, fontsize=title_fontsize,
                color="black", ha="left", va="bottom",
            )

    plt.tight_layout()

    for arrow_data in arrow_info:
        try:
            source_disp = arrow_data["source_ax"].transData.transform(
                (arrow_data["source_x"], arrow_data["source_y"])
            )
            target_disp = arrow_data["target_ax"].transData.transform(
                (arrow_data["target_x"], arrow_data["target_y"])
            )

            source_fig = fig.transFigure.inverted().transform(source_disp)
            target_fig = fig.transFigure.inverted().transform(target_disp)

            arrow = FancyArrowPatch(
                source_fig, target_fig,
                arrowstyle="->, head_length=4, head_width=5",
                lw=primary_lw,
                color="k",
                alpha=0.5,
                transform=fig.transFigure,
                zorder=1000,
            )

            fig.patches.append(arrow)
        except Exception as e:
            warnings.warn(f"Could not create arrow: {e}", stacklevel=2)
            continue

    fig.suptitle(
        f"Typical {variable}: {round(latitude, 2)}, {round(longitude, 2)} "
        f"- Year Range: {multi_year_data['Year'].min()}-{multi_year_data['Year'].max()}",
        fontsize=10, x=0.018, y=0.99, ha="left", va="bottom",
    )

    if output_path:
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        logger.info("Plot saved: %s", output_path)

    return fig
