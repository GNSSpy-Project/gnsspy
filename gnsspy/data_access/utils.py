

import os
import netrc as _netrc
import requests

from .config import BASE_URL, NETRC_FILE 





STATION_CODES = {
    "ABMF": "ABMF00GLP", "ABPO": "ABPO00MDG", "ADE1": "ADE100AUS", "ADIS": "ADIS00ETH",
    "AGGO": "AGGO00ARG", "AIRA": "AIRA00JPN", "AJAC": "AJAC00FRA", "ALBH": "ALBH00CAN",
    "ALGO": "ALGO00CAN", "ALIC": "ALIC00AUS", "ALRT": "ALRT00CAN", "AMC2": "AMC200USA",
    "AMC4": "AMC400USA", "ANKR": "ANKR00TUR", "ANMG": "ANMG00MYS", "ANTC": "ANTC00CHL",
    "AOML": "AOML00USA", "AREG": "AREG00PER", "AREQ": "AREQ00PER", "AREV": "AREV00PER",
    "ARHT": "ARHT00ATA", "ARTU": "ARTU00RUS", "ARUC": "ARUC00ARM", "ASC1": "ASC100SHN",
    "ASCG": "ASCG00SHN", "ASPA": "ASPA00USA", "ATRU": "ATRU00KAZ", "AUCK": "AUCK00NZL",
    "AZU1": "AZU100USA", "BADG": "BADG00RUS", "BAHR": "BAHR00BHR", "BAIE": "BAIE00CAN",
    "BAKE": "BAKE00CAN", "BAKO": "BAKO00IDN", "BAMF": "BAMF00CAN", "BAN2": "BAN200IND",
    "BARH": "BARH00USA", "BELE": "BELE00BRA", "BHR1": "BHR100BHR", "BHR2": "BHR200BHR",
    "BHR3": "BHR300BHR", "BHR4": "BHR400BHR", "BIK0": "BIK000KGZ", "BILI": "BILI00RUS",
    "BILL": "BILL00USA", "BJCO": "BJCO00BEN", "BJFS": "BJFS00CHN", "BJNM": "BJNM00CHN",
    "BLYT": "BLYT00USA", "BNOA": "BNOA00IDN", "BOAV": "BOAV00BRA", "BOGI": "BOGI00POL",
    "BOGT": "BOGT00COL", "BOR1": "BOR100POL", "BRAZ": "BRAZ00BRA", "BREW": "BREW00USA",
    "BRFT": "BRFT00BRA", "BRMU": "BRMU00GBR", "BRST": "BRST00FRA", "BRUN": "BRUN00BRN",
    "BRUS": "BRUS00BEL", "BRUX": "BRUX00BEL", "BSHM": "BSHM00ISR", "BTNG": "BTNG00IDN",
    "BUCU": "BUCU00ROU", "BUE2": "BUE200ARG", "BZRG": "BZRG00ITA", "CAGL": "CAGL00ITA",
    "CAGS": "CAGS00CAN", "CAGZ": "CAGZ00ITA", "CAS1": "CAS100ATA", "CCJ2": "CCJ200JPN",
    "CCJM": "CCJM00JPN", "CEBR": "CEBR00ESP", "CEDU": "CEDU00AUS", "CFAG": "CFAG00ARG",
    "CGGN": "CGGN00NGA", "CHAN": "CHAN00CHN", "CHAT": "CHAT00NZL", "CHIL": "CHIL00USA",
    "CHOF": "CHOF00JPN", "CHPG": "CHPG00BRA", "CHPI": "CHPI00BRA", "CHTI": "CHTI00NZL",
    "CHUM": "CHUM00KAZ", "CHUR": "CHUR00CAN", "CHWK": "CHWK00CAN", "CIBG": "CIBG00IDN",
    "CIC1": "CIC100MEX", "CIT1": "CIT100USA", "CKIS": "CKIS00COK", "CKSV": "CKSV00TWN",
    "CLAR": "CLAR00USA", "CMP9": "CMP900USA", "CMUM": "CMUM00THA", "CNMR": "CNMR00USA",
    "COCO": "COCO00AUS", "CONZ": "CONZ00CHL", "CORD": "CORD00ARG", "COSO": "COSO00USA",
    "COTE": "COTE00ATA", "COYQ": "COYQ00CHL", "CPNM": "CPNM00THA", "CPVG": "CPVG00CPV",
    "CRAO": "CRAO00UKR", "CRFP": "CRFP00USA", "CRO1": "CRO100VIR", "CUSV": "CUSV00THA",
    "CUT0": "CUT000AUS", "CUUT": "CUUT00THA", "CZTG": "CZTG00ATF", "DAE2": "DAE200KOR",
    "DAEJ": "DAEJ00KOR", "DAKR": "DAKR00SEN", "DARW": "DARW00AUS", "DAV1": "DAV100ATA",
    "DEAR": "DEAR00ZAF", "DGAR": "DGAR00GBR", "DGAV": "DGAV00GBR", "DHLG": "DHLG00USA",
    "DJIG": "DJIG00DJI", "DLF1": "DLF100NLD", "DLTV": "DLTV00VNM", "DRAG": "DRAG00ISR",
    "DRAO": "DRAO00CAN", "DUBO": "DUBO00CAN", "DUBR": "DUBR00HRV", "DUM1": "DUM100ATA",
    "DUND": "DUND00NZL", "DYNG": "DYNG00GRC", "EBRE": "EBRE00ESP", "EIL3": "EIL300USA",
    "EIL4": "EIL400USA", "EISL": "EISL00CHL", "EPRT": "EPRT00USA", "ESCU": "ESCU00CAN",
    "EUSM": "EUSM00MYS", "FAA1": "FAA100PYF", "FAIR": "FAIR00USA", "FALE": "FALE00WSM",
    "FALK": "FALK00FLK", "FFMJ": "FFMJ00DEU", "FLIN": "FLIN00CAN", "FLRS": "FLRS00PRT",
    "FUNC": "FUNC00PRT", "GALA": "GALA00ECU", "GAMB": "GAMB00PYF", "GAMG": "GAMG00KOR",
    "GANP": "GANP00SVK", "GARI": "GARI00KOR", "GCGO": "GCGO00USA", "GLPS": "GLPS00ECU",
    "GLSV": "GLSV00UKR", "GMSD": "GMSD00JPN", "GODN": "GODN00USA", "GODZ": "GODZ00USA",
    "GOLD": "GOLD00USA", "GOP6": "GOP600CZE", "GOP7": "GOP700CZE", "GOUG": "GOUG00SHN",
    "GRAC": "GRAC00FRA", "GRAS": "GRAS00FRA", "GRAZ": "GRAZ00AUT", "GUAM": "GUAM00GUM",
    "GUAO": "GUAO00CHN", "GUAT": "GUAT00GTM", "HARB": "HARB00ZAF", "HKSL": "HKSL00HKG",
    "HKWS": "HKWS00HKG", "HLFX": "HLFX00CAN", "HMDT": "HMDT00TUN", "HNLC": "HNLC00USA",
    "HNPT": "HNPT00USA", "HOB2": "HOB200AUS", "HOFN": "HOFN00ISL", "HOLB": "HOLB00CAN",
    "HRAO": "HRAO00ZAF", "HUEG": "HUEG00DEU", "HYDE": "HYDE00IND", "IISC": "IISC00IND",
    "INVK": "INVK00CAN", "IPSA": "IPSA00BRA", "IQAL": "IQAL00CAN", "IRKJ": "IRKJ00RUS",
    "IRKM": "IRKM00RUS", "IRKT": "IRKT00RUS", "ISBA": "ISBA00TUR", "ISTA": "ISTA00TUR",
    "JFNG": "JFNG00CHN", "JOG2": "JOG200IDN", "JOZE": "JOZE00POL", "JPLM": "JPLM00USA",
    "JPRE": "JPRE00ZAF", "KARR": "KARR00AUS", "KAT1": "KAT100AUS", "KERG": "KERG00ATF",
    "KIR0": "KIR000SWE", "KIR8": "KIR800SWE", "KIRI": "KIRI00KIR", "KIRV": "KIRV00FIN",
    "KIT3": "KIT300UZB", "KITG": "KITG00UZB", "KMNM": "KMNM00JPN", "KODK": "KODK00USA",
    "KOKB": "KOKB00USA", "KOSG": "KOSG00NLD", "KOUR": "KOUR00GUF", "KRGG": "KRGG00ATF",
    "KRS1": "KRS100TUR", "KUAQ": "KUAQ00GRL", "KZN2": "KZN200RUS", "LAE1": "LAE100PNG",
    "LAMA": "LAMA00POL", "LAUT": "LAUT00FJI", "LBCH": "LBCH00USA", "LCK3": "LCK300USA",
    "LHAZ": "LHAZ00CHN", "LMMF": "LMMF00MTQ", "LPAL": "LPAL00ESP", "LPGS": "LPGS00ARG",
    "LUCK": "LUCK00IND", "LWCK": "LWCK00CAN", "MAC1": "MAC100AUS", "MADR": "MADR00ESP",
    "MAG0": "MAG000RUS", "MAHZ": "MAHZ00ISR", "MAL2": "MAL200KEN", "MALO": "MALO00VUT",
    "MANA": "MANA00NIC", "MAR6": "MAR600SWE", "MAR7": "MAR700SWE", "MARS": "MARS00FRA",
    "MAS1": "MAS100ESP", "MAT1": "MAT100ITA", "MATE": "MATE00ITA", "MAUI": "MAUI00USA",
    "MAW1": "MAW100ATA", "MAYG": "MAYG00MYT", "MBAR": "MBAR00UGA", "MCM4": "MCM400ATA",
    "MCNL": "MCNL00USA", "MCIL": "MCIL00USA", "MDO1": "MDO100USA", "MDVJ": "MDVJ00RUS",
    "MEDI": "MEDI00ITA", "MERS": "MERS00TUR", "METG": "METG00FIN", "METS": "METS00FIN",
    "MGUE": "MGUE00ARG", "MID1": "MID100USA", "MIK3": "MIK300JPN", "MIKL": "MIKL00UKR",
    "MKEA": "MKEA00USA", "MLVL": "MLVL00VUT", "MOBS": "MOBS00AUS", "MOBN": "MOBN00GAB",
    "MOGZ": "MOGZ00ZMB", "MORP": "MORP00GBR", "MOSA": "MOSA00ZAF", "MRO1": "MRO100AUS",
    "NAIN": "NAIN00CAN", "NANO": "NANO00CAN", "NAUR": "NAUR00NRU", "NAVI": "NAVI00IND",
    "NCKU": "NCKU00TWN", "NDSK": "NDSK00RUS", "NICO": "NICO00CYP", "NIST": "NIST00USA",
    "NIUM": "NIUM00NIU", "NIU1": "NIU100NIU", "NKLG": "NKLG00GAB", "NLIB": "NLIB00USA",
    "NNOR": "NNOR00AUS", "NOT1": "NOT100ITA", "NOVM": "NOVM00RUS", "NRIL": "NRIL00RUS",
    "NRC1": "NRC100CAN", "NRMD": "NRMD00NCL", "NTSC": "NTSC00USA", "NTUS": "NTUS00SGP",
    "NVSK": "NVSK00RUS", "NYA1": "NYA100NOR", "NYA2": "NYA200NOR", "NYAL": "NYAL00NOR",
    "OAK1": "OAK100USA", "OAK2": "OAK200USA", "OATT": "OATT00USA", "OHI2": "OHI200ATA",
    "OHI3": "OHI300ATA", "OHIG": "OHIG00ATA", "ONSA": "ONSA00SWE", "OP71": "OP7100FRA",
    "OPMT": "OPMT00FRA", "OSLS": "OSLS00NOR", "OUS2": "OUS200NZL", "OVE6": "OVE600SWE",
    "P101": "P10100BRA", "P472": "P47200USA", "PADO": "PADO00ITA", "PALM": "PALM00ATA",
    "PARK": "PARK00AUS", "PARC": "PARC00CHL", "PAT0": "PAT000GRC", "PBRI": "PBRI00ZAF",
    "PDEL": "PDEL00PRT", "PENC": "PENC00HUN", "PERT": "PERT00AUS", "PETP": "PETP00RUS",
    "PETS": "PETS00RUS", "PFAN": "PFAN00USA", "Phil": "PHIL00USA", "PICL": "PICL00CAN",
    "PIE1": "PIE100USA", "PIMO": "PIMO00PHL", "PNGM": "PNGM00PNG", "POAL": "POAL00BRA",
    "POL2": "POL200KGZ", "POLV": "POLV00UKR", "POTS": "POTS00DEU", "POVE": "POVE00BRA",
    "PPPC": "PPPC00PHL", "PRDS": "PRDS00CAN", "PRE1": "PRE100ZAF", "PRE3": "PRE300ZAF",
    "PRE4": "PRE400ZAF", "PRGU": "PRGU00CZE", "PTAG": "PTAG00PHL", "PTBB": "PTBB00DEU",
    "PTGG": "PTGG00PHL", "PTVL": "PTVL00VUT", "QAQ1": "QAQ100GRL", "QIKI": "QIKI00CAN",
    "QUAN": "QUAN00CHN", "QUAQ": "QUAQ00GRL", "QUI1": "QUI100ECU", "QUIT": "QUIT00ECU",
    "RABT": "RABT00MAR", "RAMO": "RAMO00ISR", "RARO": "RARO00COK", "RBAY": "RBAY00ZAF",
    "RCMN": "RCMN00KEN", "RECF": "RECF00BRA", "REUN": "REUN00REU", "REYK": "REYK00ISL",
    "RGDG": "RGDG00ARG", "RIO2": "RIO200ARG", "RIOG": "RIOG00ARG", "ROAG": "ROAG00ESP",
    "ROCK": "ROCK00USA", "ROUG": "ROUG00GLP", "SALU": "SALU00BRA", "SAMO": "SAMO00WSM",
    "SANT": "SANT00CHL", "SASK": "SASK00CAN", "SAVO": "SAVO00BRA", "SCOR": "SCOR00GRL",
    "SCRZ": "SCRZ00BOL", "SCTB": "SCTB00ATA", "SCUB": "SCUB00CUB", "SEJN": "SEJN00KOR",
    "SELE": "SELE00KAZ", "SEY2": "SEY200SYC", "SEYG": "SEYG00SYC", "SFDM": "SFDM00USA",
    "SFER": "SFER00ESP", "SGOC": "SGOC00LKA", "SGPO": "SGPO00USA", "SHAO": "SHAO00CHN",
    "SHE2": "SHE200CAN", "SIMO": "SIMO00ZAF", "SIN1": "SIN100SGP", "SMST": "SMST00JPN",
    "SNI1": "SNI100USA", "SOD3": "SOD300FIN", "SOFI": "SOFI00BGR", "SOLO": "SOLO00SLB",
    "SPK1": "SPK100USA", "SPT0": "SPT000SWE", "SPTU": "SPTU00BRA", "SSIA": "SSIA00SLV",
    "STFU": "STFU00USA", "STHL": "STHL00GBR", "STJ3": "STJ300CAN", "STJO": "STJO00CAN",
    "STK2": "STK200JPN", "STR1": "STR100AUS", "STR2": "STR200AUS", "SULP": "SULP00UKR",
    "SUTH": "SUTH00ZAF", "SUTM": "SUTM00ZAF", "SUWN": "SUWN00KOR", "SVTL": "SVTL00RUS",
    "SYDN": "SYDN00AUS", "SYOG": "SYOG00ATA", "TABL": "TABL00USA", "TAEJ": "TAEJ00KOR",
    "TAH1": "TAH100PYF", "TANA": "TANA00ETH", "TASH": "TASH00UZB", "TCMS": "TCMS00TWN",
    "TDOU": "TDOU00ZAF", "TEHN": "TEHN00IRN", "THTG": "THTG00PYF", "THTI": "THTI00PYF",
    "THU1": "THU100GRL", "THU2": "THU200GRL", "THU3": "THU300GRL", "TID1": "TID100AUS",
    "TIDB": "TIDB00AUS", "TIT2": "TIT200DEU", "TIXI": "TIXI00RUS", "TLSE": "TLSE00FRA",
    "TLSG": "TLSG00FRA", "TNML": "TNML00TWN", "TONG": "TONG00TON", "TOPL": "TOPL00BRA",
    "TORP": "TORP00USA", "TOW2": "TOW200AUS", "TRAB": "TRAB00TUR", "TRAK": "TRAK00USA",
    "TRO1": "TRO100NOR", "TROM": "TROM00NOR", "TSK2": "TSK200JPN", "TSKB": "TSKB00JPN",
    "TUBI": "TUBI00TUR", "TUVA": "TUVA00TUV", "TWTF": "TWTF00TWN", "UCAL": "UCAL00CAN",
    "UCLP": "UCLP00USA", "UCLU": "UCLU00CAN", "UFPR": "UFPR00BRA", "ULAB": "ULAB00MNG",
    "ULDI": "ULDI00ZAF", "UNB3": "UNB300CAN", "UNBD": "UNBD00CAN", "UNBJ": "UNBJ00CAN",
    "UNBN": "UNBN00CAN", "UNSA": "UNSA00ARG", "UNX2": "UNX200AUS", "UNX3": "UNX300AUS",
    "URAL": "URAL00RUS", "URUM": "URUM00CHN", "USN3": "USN300USA", "USN7": "USN700USA",
    "USN8": "USN800USA", "USN9": "USN900USA", "USNO": "USNO00USA", "USUD": "USUD00JPN",
    "UTQI": "UTQI00USA", "UZHL": "UZHL00UKR", "VACS": "VACS00MUS", "VALD": "VALD00CAN",
    "VESL": "VESL00ATA", "VILL": "VILL00ESP", "VIS0": "VIS000SWE", "VNDP": "VNDP00USA",
    "VOIM": "VOIM00MDG", "WAB2": "WAB200CHE", "WARK": "WARK00NZL", "WARN": "WARN00DEU",
    "WDC5": "WDC500USA", "WDC6": "WDC600USA", "WES2": "WES200USA", "WGTN": "WGTN00NZL",
    "WHC1": "WHC100USA", "WHIT": "WHIT00CAN", "WIDC": "WIDC00USA", "WILL": "WILL00CAN",
    "WIND": "WIND00NAM", "WLSN": "WLSN00USA", "WROC": "WROC00POL", "WSRT": "WSRT00NLD",
    "WTZ3": "WTZ300DEU", "WTZA": "WTZA00DEU", "WTZR": "WTZR00DEU", "WTZS": "WTZS00DEU",
    "WTZZ": "WTZZ00DEU", "WUH2": "WUH200CHN", "WUHN": "WUHN00CHN", "XMIS": "XMIS00AUS",
    "YAKT": "YAKT00RUS", "YAR1": "YAR100AUS", "YAR2": "YAR200AUS", "YAR3": "YAR300AUS",
    "YARR": "YARR00AUS", "YEBE": "YEBE00ESP", "YEL2": "YEL200CAN", "YELL": "YELL00CAN",
    "YIBL": "YIBL00OMN", "YKRO": "YKRO00CIV", "YONS": "YONS00KOR", "YSSK": "YSSK00RUS",
    "ZAMB": "ZAMB00ZMB", "ZECK": "ZECK00RUS", "ZIM2": "ZIM200CHE", "ZIM3": "ZIM300CHE",
    "ZIMJ": "ZIMJ00CHE", "ZIMM": "ZIMM00CHE", "ZWE2": "ZWE200RUS",
}

def get_full_code(station_code):
    """
    Converts 4-character station code to 9 characters
    """
    station_upper = station_code.upper()
    
    if len(station_upper) == 9:
        return station_upper
    
    if len(station_upper) == 4:
        return STATION_CODES.get(station_upper, f"{station_upper}00XXX")
    
    return station_upper






def save_credentials(username, password):
    """
    Save user credentials to .netrc file
    """
    try:
        with open(NETRC_FILE, 'w') as f:
            f.write("machine urs.earthdata.nasa.gov\n")
            f.write(f"login {username}\n")
            f.write(f"password {password}\n")
        

        if os.name != 'nt':
            os.chmod(NETRC_FILE, 0o600)
        
        return True, "Credentials saved successfully"
    
    except Exception as e:
        return False, f"Save error: {str(e)}"


def test_credentials(username, password):
    """
    Test NASA login credentials
    """
    try:

        test_url = "https://urs.earthdata.nasa.gov/profile"
        response = requests.get(test_url, auth=(username, password), timeout=30)
        
        if response.status_code == 200:
            return True, "Login successful"
        elif response.status_code == 401:
            return False, "Incorrect username or password"
        elif response.status_code == 403:
            return False, "CDDIS authorization required\nhttps://cddis.nasa.gov/"
        else:
            return False, f"Unknown error: {response.status_code}"
    
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def load_credentials():
    """Load NASA Earthdata credentials from the configured .netrc file."""
    if not os.path.exists(NETRC_FILE):
        return None, None

    try:
        auth = _netrc.netrc(NETRC_FILE).authenticators("urs.earthdata.nasa.gov")
        if auth is None:
            return None, None
        username, _, password = auth
        return username, password
    except Exception:

        try:
            with open(NETRC_FILE, 'r') as f:
                lines = f.readlines()
            username = None
            password = None
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == 'login':
                    username = parts[1]
                elif len(parts) >= 2 and parts[0] == 'password':
                    password = parts[1]
            return username, password
        except Exception:
            return None, None
