"""Observation code mapping between RINEX 2 (2-char) and RINEX 3 (3-char).

RINEX 2 codes are two characters: <type><band>
  type:  C = pseudorange (C/A)
         P = pseudorange (P code)
         L = carrier phase
         D = doppler
         S = signal strength
  band:  1, 2, 5, 6, 7, 8

RINEX 3 codes are three characters: <type><band><attribute>
  attribute encodes tracking mode (C, P, W, X, S, L, Q, I, ...).

The mapping is inherently ambiguous (RINEX 2 -> 3) and lossy (3 -> 2).
We use the conventions documented in RINEX 3.04 (Table A2) and the IGS
RINEX-2 to RINEX-3 mapping commonly applied by tools like teqc / gfzrnx.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple












GLONASS_FREQ_CHANNELS: Dict[str, int] = {
    "R01":  1, "R02": -4, "R03":  5, "R04":  6,
    "R05":  1, "R06": -4, "R07":  5, "R08":  6,
    "R09": -2, "R10": -7, "R11":  0, "R12": -1,
    "R13": -2, "R14": -7, "R15":  0, "R16": -1,
    "R17":  4, "R18": -3, "R19":  3, "R20":  2,
    "R21":  4, "R22": -3, "R23":  3, "R24":  2,

    "R25":  6, "R26": -5,
}


























_R3_TO_R2_PRESEED_GPS = {
    "C1C": "C1", "C1S": "C1", "C1L": "C1", "C1X": "C1",
    "C1P": "P1", "C1W": "P1", "C1Y": "P1", "C1M": "P1",
    "L1C": "L1", "L1S": "L1", "L1L": "L1", "L1X": "L1",
    "L1P": "L1", "L1W": "L1", "L1Y": "L1", "L1M": "L1", "L1N": "L1",
    "D1C": "D1", "D1S": "D1", "D1L": "D1", "D1X": "D1",
    "D1P": "D1", "D1W": "D1", "D1Y": "D1", "D1M": "D1", "D1N": "D1",
    "S1C": "S1", "S1S": "S1", "S1L": "S1", "S1X": "S1",
    "S1P": "S1", "S1W": "S1", "S1Y": "S1", "S1M": "S1", "S1N": "S1",
    "C2C": "C2", "C2S": "C2", "C2L": "C2", "C2X": "C2", "C2M": "C2",
    "C2D": "P2", "C2P": "P2", "C2W": "P2", "C2Y": "P2",
    "L2C": "L2", "L2S": "L2", "L2L": "L2", "L2X": "L2", "L2M": "L2",
    "L2D": "L2", "L2P": "L2", "L2W": "L2", "L2Y": "L2", "L2N": "L2",
    "D2C": "D2", "D2S": "D2", "D2L": "D2", "D2X": "D2", "D2M": "D2",
    "D2D": "D2", "D2P": "D2", "D2W": "D2", "D2Y": "D2", "D2N": "D2",
    "S2C": "S2", "S2S": "S2", "S2L": "S2", "S2X": "S2", "S2M": "S2",
    "S2D": "S2", "S2P": "S2", "S2W": "S2", "S2Y": "S2", "S2N": "S2",
}

_R3_TO_R2_PRESEED_GLO = {
    "C1C": "C1", "C1P": "P1",
    "L1C": "L1", "L1P": "L1",
    "D1C": "D1", "D1P": "D1",
    "S1C": "S1", "S1P": "S1",
    "C2C": "C2", "C2P": "P2",
    "L2C": "L2", "L2P": "L2",
    "D2C": "D2", "D2P": "D2",
    "S2C": "S2", "S2P": "S2",
}


def r3_to_r2_code(system: str, code3: str) -> Optional[str]:
    """Translate a 3-char RINEX 3 code to a 2-char RINEX 2 code.

    Returns None if the code cannot be expressed (e.g. unknown type).
    Generic rule: drop the attribute character.
    """
    if len(code3) != 3:
        return None
    if system == "G":
        if code3 in _R3_TO_R2_PRESEED_GPS:
            return _R3_TO_R2_PRESEED_GPS[code3]
    if system == "R":
        if code3 in _R3_TO_R2_PRESEED_GLO:
            return _R3_TO_R2_PRESEED_GLO[code3]

    t, b, _attr = code3[0], code3[1], code3[2]
    if t in "CLDS" and b in "12345678":
        return t + b
    return None











_DEFAULT_ATTR_GPS = {
    "1": "C",
    "2": "X",
    "5": "X",
}
_DEFAULT_ATTR_GLO = {
    "1": "C",
    "2": "C",
    "3": "Q",
}
_DEFAULT_ATTR_GAL = {
    "1": "X", "5": "X", "6": "X", "7": "X", "8": "X",
}
_DEFAULT_ATTR_BDS = {
    "1": "I", "2": "I", "5": "X", "6": "I", "7": "I", "8": "X",
}
_DEFAULT_ATTR_QZS = {
    "1": "C", "2": "X", "5": "X", "6": "X",
}
_DEFAULT_ATTR_IRN = {
    "5": "A", "9": "A",
}
_DEFAULT_ATTR_SBAS = {
    "1": "C", "5": "X",
}


def _gps_attr(band: str, type_char: str, r2_set: Set[str]) -> str:
    """Pick the GPS attribute for a given (type, band) given all RINEX 2 codes
    present in the file (used to disambiguate L1/L2/D1/D2/S1/S2 when paired
    with P codes)."""
    if band == "1":
        if type_char == "C":
            return "C"
        if type_char == "P":
            return "W"


        return "W" if "P1" in r2_set else "C"
    if band == "2":
        if type_char == "C":

            return "X"
        if type_char == "P":
            return "W"


        return "W" if "P2" in r2_set else "X"
    if band == "5":
        return "X"
    return "X"


def _glo_attr(band: str, type_char: str, r2_set: Set[str]) -> str:
    if band in ("1", "2"):
        if type_char == "C":
            return "C"
        if type_char == "P":
            return "P"

        return "P" if f"P{band}" in r2_set else "C"
    if band == "3":
        return "Q"
    return "C"


def r2_to_r3_code(system: str, code2: str, r2_set: Set[str]) -> Optional[str]:
    """Translate a 2-char RINEX 2 code to a 3-char RINEX 3 code.

    Parameters
    ----------
    system : str
        Single-letter system code (G, R, E, C, J, I, S).
    code2 : str
        The RINEX 2 observation code, e.g. "C1", "L2", "P2", "S5".
    r2_set : Set[str]
        All RINEX 2 codes present in the file for this system (used to
        disambiguate cases like "L1 with P1" vs "L1 with C1").
    """
    if len(code2) != 2:
        return None
    type_char, band = code2[0], code2[1]
    if type_char not in "CLDSP" or band not in "12345678":
        return None



    out_type = "C" if type_char == "P" else type_char

    if system == "G":
        attr = _gps_attr(band, type_char, r2_set)
    elif system == "R":
        attr = _glo_attr(band, type_char, r2_set)
    elif system == "E":
        attr = _DEFAULT_ATTR_GAL.get(band, "X")
    elif system == "C":
        attr = _DEFAULT_ATTR_BDS.get(band, "I")
    elif system == "J":
        attr = _DEFAULT_ATTR_QZS.get(band, "X")
    elif system == "I":
        attr = _DEFAULT_ATTR_IRN.get(band, "A")
    elif system == "S":
        attr = _DEFAULT_ATTR_SBAS.get(band, "C")
    else:
        attr = "C"

    return f"{out_type}{band}{attr}"


def build_r2_to_r3_map(system: str, r2_codes: Iterable[str]) -> Dict[str, str]:
    """Build a {r2_code: r3_code} map for one system, given the codes present."""
    r2_set = set(r2_codes)
    out: Dict[str, str] = {}
    for c2 in r2_codes:
        c3 = r2_to_r3_code(system, c2, r2_set)
        if c3 is not None:
            out[c2] = c3
    return out


def build_r3_to_r2_map(system: str, r3_codes: Iterable[str]) -> Tuple[Dict[str, str], List[str]]:
    """Build a {r3_code: r2_code} map for one system.

    When several r3 codes map to the same r2 code, all of them point to it
    and the writer will pick the first non-blank value at write time.

    Returns
    -------
    (mapping, unmapped) where ``unmapped`` is the list of r3 codes that have
    no RINEX 2 equivalent.
    """
    mapping: Dict[str, str] = {}
    unmapped: List[str] = []
    for c3 in r3_codes:
        c2 = r3_to_r2_code(system, c3)
        if c2 is None:
            unmapped.append(c3)
        else:
            mapping[c3] = c2
    return mapping, unmapped
