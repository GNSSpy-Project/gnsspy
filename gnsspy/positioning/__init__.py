"""Positioning utilities for GNSSpy v3.

The preferred imports are explicit submodule imports, for example:

    from gnsspy.positioning.spp import spp
    from gnsspy.positioning.observations import gnssDataframe
"""

__all__ = [
    "spp",
    "standard_point_positioning",
    "gnssDataframe",
    "build_gnss_dataframe",
    "build_observation_orbit_dataframe",
    "_observation_picker",
    "_observation_picker_by_band",
    "pick_observations",
    "pick_observation_by_band",
    "_adjustment",
    "least_squares_adjustment",
]


def __getattr__(name):
    if name in {"spp", "standard_point_positioning"}:
        from gnsspy.positioning.spp import spp, standard_point_positioning
        return {"spp": spp, "standard_point_positioning": standard_point_positioning}[name]

    if name in {
        "gnssDataframe",
        "build_gnss_dataframe",
        "build_observation_orbit_dataframe",
        "_observation_picker",
        "_observation_picker_by_band",
        "pick_observations",
        "pick_observation_by_band",
    }:
        from gnsspy.positioning import observations
        return getattr(observations, name)

    if name in {"_adjustment", "least_squares_adjustment"}:
        from gnsspy.positioning import adjustment
        return getattr(adjustment, name)

    raise AttributeError(f"module 'gnsspy.positioning' has no attribute {name!r}")
