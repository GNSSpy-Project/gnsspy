import sys
import datetime
from gnsspy.utils.date import (gpsweekday, datetime2doy)
from gnsspy.data.IGS import IGS


def get_long_filename(date, product_type="SP3", agency="IGS", project="OPS", solution="FIN",
                      sampling=None, duration=None, hour=0, minute=0):
    """Generate a name; use product discovery rather than assuming it exists."""
    from gnsspy.utils.product_files import long_product_filename
    return long_product_filename(date, product_type.lower(), agency, project, solution,
                                 duration, sampling, hour, minute)


def obsFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    year_short = str(date.year)[-2:]


    rinexFile = stationName + doy + "0." + year_short + "o"

    if zipped:
        rinexFile = rinexFile + ".Z"

    return rinexFile


def _precise_filename(epoch, product, kind, sampling=None, solution=None, project=None):
    from gnsspy.utils.product_files import (as_date, product_spec, long_product_filename)
    epoch = as_date(epoch)
    center, selected_project, selected_solution, version = product_spec(product)
    if center is None:
        raise ValueError("auto selects existing products; it cannot identify one filename")
    solution = str(solution or selected_solution or "FIN").upper()
    solution = {"FINAL":"FIN", "RAPID":"RAP", "ULTRA-RAPID":"ULT"}.get(solution, solution)
    if selected_solution and solution != selected_solution:
        raise ValueError("Requested series conflicts with solution")
    project = project or selected_project
    if epoch >= datetime.date(2022,11,27) or selected_project is not None:
        return long_product_filename(epoch,kind,center,project,solution,
                                     sampling=sampling,version=version or "0")
    gps_week, _ = gpsweekday(epoch, Datetime=True)
    dow = (epoch-datetime.date(1980,1,6)).days % 7
    if solution in {'RAP','ULT'} and center != 'IGS':
        raise ValueError('Legacy RAP/ULT naming is only defined here for IGS; supply an explicit modern series or a local path')
    prefix = {'RAP':'igr','ULT':'igu'}.get(solution, str(product).lower()[:3])
    if prefix == 'cod' and str(product).lower() == 'code':
        prefix = 'cod'
    extension = '.clk_05s' if kind == 'clk' and sampling == '05S' else f'.{kind}'
    return f"{prefix}{int(gps_week):04d}{dow}" + ('_00' if solution == 'ULT' else '') + extension


def sp3FileName(epoch, product="igs", *, sampling=None, solution=None, project=None):
    """Deterministic naming helper. It does not infer availability from file age."""
    return _precise_filename(epoch, product, "sp3", sampling, solution, project)


def clockFileName(epoch, interval=30, product="cod", *, sampling=None, solution=None, project=None):
    """Generate a clock name without silently changing the requested centre."""
    if sampling is None:
        if isinstance(interval,bool) or not isinstance(interval,(int,float)) or interval <= 0 or interval != int(interval):
            raise ValueError('clock interval must be a positive integral number of seconds')
        interval = int(interval)
        if interval % 60 == 0 and interval // 60 < 100:
            sampling = f'{interval//60:02d}M'
        elif interval < 100:
            sampling = f'{interval:02d}S'
        else:
            raise ValueError('clock interval cannot be expressed by the two-digit sampling token')
    return _precise_filename(epoch, product, "clk", sampling, solution, project)


def ionFileName(date, product="igs", zipped=False, *, solution="auto", sampling=None, legacy=None):
    """Generate a legacy/modern GIM candidate, never infer its availability.

    Before GPS week 2238 the default is short naming; afterwards it is long
    naming. A full product or a legacy prefix can pin the solution. For an
    unpinned centre, this deterministic helper chooses FIN (not a prediction).
    Use acquire_ionosphere for actual availability and original local paths.
    """
    from gnsspy.utils.ionex_files import ionex_filename, ionex_request
    request = ionex_request(product, solution)
    selected = request.solutions[0]

    series = product
    if len(request.solutions) != 1:
        solution = 'final'
    return ionex_filename(date, series, solution=solution, sampling=sampling,
                          legacy=legacy, zipped=zipped)

def navFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    year_short = str(date.year)[-2:]
    rinexFile = stationName + doy + "0." + year_short + "n"
    if zipped:
        rinexFile = rinexFile + ".Z"
    return rinexFile

def nav3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    siteInfo = IGS(stationName)
    if stationName.upper() == "BRDC":
        rinexFile = "BRDC00IGS_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    else:
        rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    if zipped:
        rinexFile = rinexFile + ".gz"
    return rinexFile

def obs3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    siteInfo = IGS(stationName)
    rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_30S_MO.crx"
    if zipped:
        rinexFile = rinexFile + ".gz"
    return rinexFile
