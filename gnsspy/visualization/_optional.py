"""Lazy access to optional interactive plotting dependencies."""
def plotly_backend():
    try:
        from gnsspy.visualization import plotly_backend as implementation
    except ImportError as exc:
        raise ImportError("This non-geographic plot uses Plotly. Install gnsspy[plotly] "
                          "or, from the source directory, '.[plotly]'.") from exc
    return implementation
