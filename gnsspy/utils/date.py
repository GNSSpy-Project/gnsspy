


"""Date and GNSS time helper functions for GNSSpy."""

import datetime

__all__ = [
    "parse_date", "gpsweekday", "gpswdtodate", "jday", "julianday2date",
    "doy", "doy2date", "datetime2doy",
]

_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%Y%m%d", "%d%m%Y",
)


def parse_date(date):
    """Return a :class:`datetime.date` from common GNSSpy date inputs.

    Accepted inputs are ``datetime.date``, ``datetime.datetime`` and strings
    in ISO style (``YYYY-MM-DD``), legacy GNSSpy style (``DD-MM-YYYY``),
    slash/dot variants, and compact ``YYYYMMDD`` or ``DDMMYYYY`` forms.
    """
    if isinstance(date, datetime.datetime):
        return date.date()
    if isinstance(date, datetime.date):
        return date
    if isinstance(date, str):
        value = date.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    raise ValueError(
        f"Invalid date format: {date!r}. Accepted examples: "
        "'2023-01-01', '01-01-2023', '20230101', datetime.date(2023, 1, 1)."
    )


def gpsweekday(date, Datetime=False):
    """Return GPS week and concatenated GPS week/day code.

    The legacy ``Datetime`` argument is retained for backwards compatibility;
    date parsing now depends on the actual input type instead.
    """
    start = datetime.date(year=1980, month=1, day=6)
    date = parse_date(date)
    diff = (date - start).days
    week = diff // 7
    day = diff % 7
    gpswday = int(f"{week}{day}")
    return week, gpswday


def gpswdtodate(gpsweekday):
    """Convert a GPS week/day code to :class:`datetime.date`."""
    gpsweekday = str(gpsweekday).strip()
    if len(gpsweekday) < 2 or not gpsweekday.isdigit():
        raise ValueError("gpsweekday must contain GPS week followed by day-of-week")
    week = int(gpsweekday[:-1])
    dow = int(gpsweekday[-1])
    if not 0 <= dow <= 6:
        raise ValueError("GPS day-of-week must be in the range 0..6")
    start = datetime.datetime(year=1980, month=1, day=6)
    return (start + datetime.timedelta(days=week * 7 + dow)).date()


def jday(date):
    """Calculate the Julian day of a given calendar date."""
    date = parse_date(date)
    year = date.year
    month = date.month
    day = date.day
    if month in (1, 2):
        month += 12
        year -= 1
    A = year // 100
    B = A // 4
    C = 2 - A + B
    E = int(365.25 * (year + 4716))
    F = int(30.6001 * (month + 1))
    return C + day + E + F - 1524.5


def julianday2date(JDay):
    """Convert Julian day to :class:`datetime.datetime`."""
    MJd = JDay - 2400000.5
    start = datetime.datetime(year=1858, month=11, day=17, hour=0, minute=0, second=0)
    return start + datetime.timedelta(days=MJd)


def doy(date) -> int:
    """Return day-of-year for a date as an integer in the range 1..366."""
    return parse_date(date).timetuple().tm_yday


def doy2date(rinexFile):
    """Extract date from common RINEX 2/3 filenames.

    The input may be a full path. RINEX 2 filenames such as ``mate0010.23o``
    and RINEX 3 long filenames such as
    ``MATE00ITA_R_20230010000_01D_30S_MO.rnx`` are supported. Compressed
    suffixes are ignored.
    """
    import os

    name = os.path.basename(str(rinexFile))
    lower = name.lower()
    for suffix in ('.gz', '.z', '.zip'):
        if lower.endswith(suffix):
            name = name[:-len(suffix)]
            lower = name.lower()
            break

    parts = name.split('_')
    if len(parts) >= 3 and len(parts[2]) >= 7 and parts[2][:7].isdigit():
        year = int(parts[2][0:4])
        day_of_year = int(parts[2][4:7])
        return datetime.date(year=year, month=1, day=1) + datetime.timedelta(days=day_of_year - 1)

    if len(name) >= 12 and name[4:7].isdigit() and name[-3:-1].isdigit():
        yy = int(name[-3:-1])
        year = 2000 + yy if yy < 80 else 1900 + yy
        day_of_year = int(name[4:7])
        return datetime.date(year=year, month=1, day=1) + datetime.timedelta(days=day_of_year - 1)

    raise ValueError(f"Could not extract date from filename: {rinexFile}")


def datetime2doy(date, string=False):
    """Return day-of-year from date/datetime/string.

    If ``string=True``, return a zero-padded three-character string.
    """
    day_of_year = doy(date)
    return f"{day_of_year:03d}" if string else day_of_year
