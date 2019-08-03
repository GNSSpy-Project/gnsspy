# ===========================================================
# ========================= imports =========================
import os
import pandas as _pd
# ===========================================================

global _FILEPATH
_FILEPATH = os.path.dirname(os.path.abspath(__file__))

def is_IGS(siteName):
    igs = _pd.read_table(_FILEPATH+"/IGSList.txt",sep="\t", names = ["CODE","SITE","COUNTRY","LATITUDE","LONGITUDE","HEIGHT"], index_col = "CODE")
    if siteName.upper() not in igs.index.tolist():
        return False
    return True

def IGS(siteName):
    igs = _pd.read_table(_FILEPATH+"/IGSList.txt",sep="\t", names = ["CODE","SITE","COUNTRY","LATITUDE","LONGITUDE","HEIGHT"], index_col = "CODE")
    if is_IGS(siteName) == True:
        siteInfo = igs[igs.index==siteName.upper()]
        return siteInfo

