"""
General configuration settings
"""

import os
from pathlib import Path


BASE_URL = "https://cddis.nasa.gov/archive/gnss/data/daily"
PRODUCTS_URL = "https://cddis.nasa.gov/archive/gnss/products"
IONOSPHERE_URL = "https://cddis.nasa.gov/archive/gnss/products/ionex"
NETRC_FILE = os.path.expanduser("~/.netrc")



PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_OUTPUT_DIR = str(PROJECT_ROOT / "data")


RINEX_VERSIONS = {
    2: "RINEX 2 (legacy format)",
    3: "RINEX 3 (modern format)"
}


FILE_TYPES = {
    'observation': {
        'name': 'Observation',
        'rinex2_ext': 'd',
        'rinex3_ext': 'MO',
        'description': 'Observation files'
    },
    'navigation': {
        'name': 'Navigation',
        'rinex2_ext': 'n',
        'rinex3_ext': 'MN',
        'description': 'Navigation files'
    }
}


SP3_CENTERS = {
    'CODE': {
        'prefix': 'COD',
        'name': 'Center for Orbit Determination in Europe',
        'description': 'High precision, recommended'
    },
    'GFZ': {
        'prefix': 'GFZ',
        'name': 'GeoForschungsZentrum Potsdam',
        'description': 'Fast processing, reliable'
    },
    'IGS': {
        'prefix': 'IGS',
        'name': 'International GNSS Service',
        'description': 'Official combination'
    },
    'WUM': {
        'prefix': 'WUM',
        'name': 'Wuhan University',
        'description': 'MGEX multi-GNSS support'
    },
    'MIT': {
        'prefix': 'MIT',
        'name': 'Massachusetts Institute of Technology',
        'description': 'Academic standard'
    }
}


ORBIT_TYPES = {
    'final': {
        'delay_days': 13,
        'accuracy': '~2-5 cm',
        'description': 'Highest precision'
    },
    'rapid': {
        'delay_days': 1,
        'accuracy': '~5 cm',
        'description': 'Fast, precise'
    },
    'ultra-rapid': {
        'delay_days': 0,
        'accuracy': '~10 cm',
        'description': 'Real-time, includes predictions'
    }
}


IONOSPHERE_TYPES = {
    'final': {
        'prefix': 'igsg',
        'delay_days': 11,
        'description': 'IGS Final (11 days delay)'
    },
    'rapid': {
        'prefix': 'igrg',
        'delay_days': 2,
        'description': 'IGS Rapid (2 days delay)'
    },
    'predicted': {
        'prefix': 'igpg',
        'delay_days': 0,
        'description': 'IGS Predicted (1-2 days ahead)'
    }
}