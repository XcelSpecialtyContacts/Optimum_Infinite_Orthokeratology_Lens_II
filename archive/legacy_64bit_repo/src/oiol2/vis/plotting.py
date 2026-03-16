from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt

ArrayLike = Union[np.ndarray, Iterable[float]]

@dataclass
class Curve:
    """
    Simple container for a plotted curve.
    Provide either:
      - x, z as 1D sequences of equal length
      - or points as an (N,2) array (columns: x, z)
    """
    label: Optional[str] = None
    x: Optional[ArrayLike] = None
    z: Optional[ArrayLike] = None
    points: Optional[np.ndarray] = None
    linestyle: str = "-"
    linewidth: float = 1.5
    color: Optional[str] = None  # let matplotlib pick if None

    def get_xz(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.points is not None:
            arr = np.asarray(self.points, dtype=float)
            if arr.ndim != 2 or arr.shape[1] != 2:
                raise ValueError("points must be shape (N,2) with columns (x,z)")
            return arr[:, 0], arr[:, 1]
        if self.x is None or self.z is None:
            raise ValueError("Provide either (points) or both (x, z)")
        x = np.asarray(self.x, dtype=float)
        z = np.asarray(self.z, dtype=float)
        if x.shape != z.shape:
            raise ValueError("x and z must have the same shape")
        return x, z


def plot_meridional_curves(
    curves: Iterable,
    *,
    title: str = "Meridional Curves",
    xlabel: str = "X (mm)",
    zlabel: str = "Z (mm)",
    equal_aspect: bool = True,
    grid: bool = False,
    xlim: Optional[Tuple[float, float]] = None,
    zlim: Optional[Tuple[float, float]] = None,
    figsize: Tuple[int, int] = (5, 5),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """
    Plot one or more meridional (x, z) curves using matplotlib.

    Args:
        curves: iterable of Curve-like objects that implement get_xz().
        title, xlabel, zlabel: labels and title
        equal_aspect: if True, enforce 1:1 aspect ratio
        grid: show grid
        xlim, zlim: optional axis limits
        figsize: figure size in inches
        save_path: optional file path to save (e.g. 'plot.png')
        show: call plt.show() at the end (ignored if running headless)
    """
    plt.figure(figsize=figsize)

    for c in curves:
        x, z = c.get_xz()
        label = getattr(c, "label", None)
        linestyle = getattr(c, "linestyle", "-")
        linewidth = getattr(c, "linewidth", 1.0)
        color = getattr(c, "color", None)

        # Only include label if it's non-empty
        if label:
            plt.plot(x, z, linestyle=linestyle, linewidth=linewidth, label=label, color=color)
        else:
            plt.plot(x, z, linestyle=linestyle, linewidth=linewidth, color=color)

    plt.xlabel(xlabel)
    plt.ylabel(zlabel)
    plt.title(title)
    if grid:
        plt.grid(True)
    if equal_aspect:
        plt.axis("equal")
    if xlim is not None:
        plt.xlim(*xlim)
    if zlim is not None:
        plt.ylim(*zlim)

    # Only show legend if at least one labeled curve exists
    handles, labels = plt.gca().get_legend_handles_labels()
    if any(labels):
        plt.legend()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()