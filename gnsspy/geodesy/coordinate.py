

import numpy as _np

__all__ = [
    "ell2cart", "cart2ell", "cart2ell_direct", "ell2topo",
    "geocentric_latitude",
]


class _Ellipsoid:
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self.f = (a - b) / a
        self.e1 = _np.sqrt((a**2 - b**2) / a**2)
        self.e2 = _np.sqrt((a**2 - b**2) / b**2)

    def radiusOfCurvature(self, phi):
        """Return meridian (M) and prime-vertical (N) radii of curvature."""
        phi = _np.deg2rad(phi)
        e2 = self.e1**2
        sin_phi2 = _np.sin(phi) ** 2
        M = self.a * (1 - e2) / (1 - e2 * sin_phi2) ** (3 / 2)
        N = self.a / _np.sqrt(1 - e2 * sin_phi2)
        return M, N



def _ellipsoid(ellipsoidName):
    axes = {
        'GRS80': [6378137.000, 6356752.314140],
        'WGS84': [6378137.000, 6356752.314245],
        'Hayford': [6378388.000, 6356911.946000],
    }[ellipsoidName]
    a, b = axes[0], axes[1]
    return _Ellipsoid(a, b)


def ell2cart(lat, lon, h, ellipsoid='GRS80'):
    """Convert geodetic coordinates to ECEF Cartesian coordinates.

    Parameters
    ----------
    lat, lon : float or array-like
        Geodetic latitude and longitude in degrees.
    h : float or array-like
        Ellipsoidal height in metres.
    ellipsoid : {'GRS80', 'WGS84', 'Hayford'}, default 'GRS80'
        Reference ellipsoid.

    Returns
    -------
    x, y, z : float or ndarray
        Earth-centred Earth-fixed Cartesian coordinates in metres.

    Notes
    -----
    The prime-vertical radius of curvature must use the first eccentricity
    squared (e^2). Earlier GNSSpy v3 prerelease code accidentally used the
    second eccentricity itself, which produced incorrect heights and latitudes
    in round-trip conversions.
    """
    ellipsoid = _ellipsoid(ellipsoid)
    lat = _np.deg2rad(lat)
    lon = _np.deg2rad(lon)

    e2 = ellipsoid.e1 ** 2
    sin_lat = _np.sin(lat)
    N = ellipsoid.a / _np.sqrt(1 - e2 * sin_lat**2)

    x = (N + h) * _np.cos(lat) * _np.cos(lon)
    y = (N + h) * _np.cos(lat) * _np.sin(lon)
    z = (N * (1 - e2) + h) * sin_lat
    return x, y, z


def cart2ell(x, y, z, ellipsoid='GRS80'):
    """Convert ECEF Cartesian coordinates to geodetic coordinates.

    Parameters
    ----------
    x, y, z : float
        Earth-centred Earth-fixed Cartesian coordinates in metres.
    ellipsoid : {'GRS80', 'WGS84', 'Hayford'}, default 'GRS80'
        Reference ellipsoid.

    Returns
    -------
    lat, lon, h : float
        Geodetic latitude and longitude in degrees and ellipsoidal height in
        metres.
    """
    ellipsoid = _ellipsoid(ellipsoid)
    lon = _np.arctan2(y, x)
    p = _np.sqrt(x**2 + y**2)
    N_init = ellipsoid.a
    h_init = _np.sqrt(x**2 + y**2 + z**2) - _np.sqrt(ellipsoid.a * ellipsoid.b)
    lat_init = _np.arctan2(z, (1 - N_init * ellipsoid.e1**2 / (N_init + h_init)) * p)
    while True:
        N = ellipsoid.a / _np.sqrt(1 - (ellipsoid.e1**2 * _np.sin(lat_init)**2))
        h = (p / _np.cos(lat_init)) - N
        lat = _np.arctan2(z, (1 - N * ellipsoid.e1**2 / (N + h)) * p)
        if _np.abs(lat_init - lat) < 1e-8 and _np.abs(h_init - h) < 1e-8:
            break
        lat_init = lat
        h_init = h
    return _np.rad2deg(lat), _np.rad2deg(lon), h


def cart2ell_direct(x, y, z, ellipsoid='GRS80'):
    """Convert ECEF Cartesian coordinates to geodetic coordinates directly."""
    ellipsoid = _ellipsoid(ellipsoid)
    lon = _np.arctan2(y, x)
    p = _np.sqrt(x**2 + y**2)
    beta = _np.arctan2(ellipsoid.a * z, ellipsoid.b * p)
    lat = _np.arctan2(
        z + ellipsoid.e2**2 * ellipsoid.b * _np.sin(beta)**3,
        p - ellipsoid.e1**2 * ellipsoid.a * _np.cos(beta)**3,
    )
    N = ellipsoid.a / _np.sqrt(1 - (ellipsoid.e1**2 * _np.sin(lat)**2))
    h = (p / _np.cos(lat)) - N
    return _np.rad2deg(lat), _np.rad2deg(lon), h


def ell2topo(lat, lon, h=None):
    """Return local east, north and up unit vectors for a geodetic position."""
    lat, lon = _np.deg2rad(lat), _np.deg2rad(lon)
    east = _np.matrix([[-_np.sin(lon)], [_np.cos(lon)], [0]])
    north = _np.matrix([
        [-_np.cos(lon) * _np.sin(lat)],
        [-_np.sin(lon) * _np.sin(lat)],
        [_np.cos(lat)],
    ])
    up = _np.matrix([
        [_np.cos(lon) * _np.cos(lat)],
        [_np.sin(lon) * _np.cos(lat)],
        [_np.sin(lat)],
    ])
    return east, north, up


def geocentric_latitude(geodetic_latitude, ellipsoid='GRS80'):
    """Convert geodetic latitude to geocentric latitude."""
    ell = _ellipsoid(ellipsoid)
    return _np.rad2deg(_np.arctan(_np.tan(_np.deg2rad(geodetic_latitude)) / (1 - ell.f) ** 2))


def _distance_euclidean(x1, y1, z1, x2, y2, z2):
    """Calculate the Euclidean distance [m] using Cartesian coordinates."""
    return _np.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
