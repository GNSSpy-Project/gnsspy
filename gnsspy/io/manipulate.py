"""
Merge split and stuffs...
"""
# ===========================================================
# ========================= imports =========================
import os
import sys
import subprocess
# ===========================================================

__all__ = ["rinex_merge"]

global _FILEPATH
_FILEPATH = os.path.dirname(os.path.abspath(__file__))

def rinex_merge(station, doy, year, directory = os.getcwd()):
    """
    Parameters:
        station: str
        doy: int
        year: int
        directory: str
    Return:
        None
    Output:
        Merged rinex observation file
    """
    rinexObsFiles=[] 
    file_start = station + str(doy)
    file_end = "."+str(year)[2:]+"o" 
    file_fullName = file_start+"0"+file_end 
    for file in os.listdir(directory):
        if file.startswith(file_start) and file.endswith(file_end):
            rinexObsFiles.append(os.path.join(directory, file))

    if os.path.join(directory,file_fullName) in rinexObsFiles:
        print("The file",file_fullName,"exists in the working directory!")
        while True:
            choice = input("Would you like to overwrite the file [Y/N]? | ")
            if choice.upper() == "Y" or choice.upper() == "Yes":
                rinexObsFiles.remove(os.path.join(directory,file_fullName))
                break
            elif choice.upper() == "N" or choice.upper() == "NO":
                sys.exit("Exiting...")
            else:
                print("Invalid choice | [Y/N]")

    with open(os.path.join(directory, file_fullName), 'w') as rinexMerged:
        with open(rinexObsFiles[0]) as rinexTemp:
            for line in rinexTemp:
                if "TIME OF LAST OBS" not in line:
                    rinexMerged.write(line)

    with open(os.path.join(directory, file_fullName), 'a') as rinexMerged:
        for rinex in range(1, len(rinexObsFiles)):
            with open(rinexObsFiles[rinex]) as rinexTemp:
                header = True
                for line in rinexTemp:
                    if header == True:
                        if "END OF HEADER" not in line:
                            continue
                        else:
                            header = False
                    else:
                        rinexMerged.write(line)

def crx2rnx(rinexFile):
    """ Converts Hatanaka format to RINEX format """
    path = os.path.dirname(os.path.abspath(__file__))
    if sys.platform=="linux" or sys.platform=="darwin":
        subprocess.call([_FILEPATH+"/CRX2RNX",rinexFile], stdin = sys.stdin)
    elif sys.platform=="windows":
        subprocess.call([_FILEPATH+"/crx2rnx.exe",rinexFile], stdin = sys.stdin)
        
