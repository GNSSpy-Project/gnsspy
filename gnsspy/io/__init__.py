"""Input/output utilities for GNSSpy v3."""

from gnsspy.io.rinex.observation import (
    read_obsFile,
    read_obsFile_v2,
    read_obsFile_v3,
    read_observation_file,
    read_observation_file_v2,
    read_observation_file_v3,
)
from gnsspy.io.rinex.navigation import (
    read_navFile,
    read_navigation_file,
)
from gnsspy.io.products.sp3 import (
    read_sp3File,
    read_sp3_file,
)
from gnsspy.io.products.clk import (
    read_clockFile,
    read_clock_file,
)
from gnsspy.io.products.ionex import (
    read_ionFile,
    read_ionex_file,
)

__all__ = [
    "read_obsFile",
    "read_obsFile_v2",
    "read_obsFile_v3",
    "read_observation_file",
    "read_observation_file_v2",
    "read_observation_file_v3",
    "read_navFile",
    "read_navigation_file",
    "read_sp3File",
    "read_sp3_file",
    "read_clockFile",
    "read_clock_file",
    "read_ionFile",
    "read_ionex_file",
]


from gnsspy.io.products.ionex import read_ionex, IonexDataset, IonexFormatError, IonexProductError
__all__ += ["read_ionex", "IonexDataset", "IonexFormatError", "IonexProductError"]
