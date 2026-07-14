"""Common in-memory representation of a RINEX observation file.

Both RINEX 2 and RINEX 3 parsers populate the same ObsData object.
Writers consume an ObsData object and emit the requested version.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple






ObsValue = Tuple[Optional[float], Optional[int], Optional[int]]


@dataclass
class ObsHeader:

    version: float = 3.04
    file_type: str = "O"
    sat_system: str = "M"
    program: str = "rinex_converter"
    run_by: str = ""
    date_str: str = ""

    marker_name: str = ""
    marker_number: str = ""
    marker_type: str = ""

    observer: str = ""
    agency: str = ""

    receiver_number: str = ""
    receiver_type: str = ""
    receiver_version: str = ""

    antenna_number: str = ""
    antenna_type: str = ""

    approx_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    antenna_delta_hen: Tuple[float, float, float] = (0.0, 0.0, 0.0)






    obs_types: Dict[str, List[str]] = field(default_factory=dict)

    interval: Optional[float] = None
    time_first_obs: Optional[datetime] = None
    time_last_obs: Optional[datetime] = None
    time_system: str = "GPS"

    leap_seconds: Optional[int] = None
    rcv_clock_offs_appl: int = 0


    signal_strength_unit: str = "DBHZ"

    phase_shifts: List[Tuple[str, str, Optional[float], Optional[List[str]]]] = field(default_factory=list)

    glonass_slots: Dict[str, int] = field(default_factory=dict)

    glonass_cod_phs_bis: Dict[str, float] = field(default_factory=dict)



    wavelength_fact: Tuple[int, int] = (1, 1)

    comments: List[str] = field(default_factory=list)


@dataclass
class ObsEpoch:
    epoch: datetime
    flag: int = 0
    rcv_clock_offset: Optional[float] = None

    obs: Dict[str, Dict[str, ObsValue]] = field(default_factory=dict)

    @property
    def num_sats(self) -> int:
        return len(self.obs)

    @property
    def sat_list(self) -> List[str]:
        return list(self.obs.keys())


@dataclass
class ObsData:
    header: ObsHeader
    epochs: List[ObsEpoch] = field(default_factory=list)

    def systems(self) -> List[str]:
        """Return sorted list of system letters present in epochs."""
        seen = set()
        for ep in self.epochs:
            for sat in ep.obs:
                seen.add(sat[0])
        return sorted(seen)

    def satellites(self, system: Optional[str] = None) -> List[str]:
        """Return the sorted list of unique satellite IDs observed.

        If *system* is given (e.g. "R"), only satellites of that system are
        returned.
        """
        seen = set()
        for ep in self.epochs:
            for sat in ep.obs:
                if system is None or sat[0] == system:
                    seen.add(sat)
        return sorted(seen)
