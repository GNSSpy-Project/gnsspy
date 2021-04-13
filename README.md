# GNSSpy
Python Toolkit for GNSS Data developed by Mustafa Serkan Isik (isikm@itu.edu.tr) and Volkan Ozbey (ozbeyv@itu.edu.tr). This project is still a work in progress. Send us your feedback if possible...

# What is GNSSpy? 
GNSSpy is a free and open source library for handling multi GNSS and different versions (2.X and 3.X) of RINEX files. It provides
Single Point Positioning (SPP) solutions by least squares adjustment using pseudo-range observations using precise ephemeris and clock files. GNSSpy can be used for editing (slicing, decimating, merging) and quality checking (multipath,ionospheric delay, SNR) for RINEX files. Ionospheric delay can be calculated from GNSS atmospheric models of IGS for single frequency RINEX data or removed using dual frequency RINEX data. It can be used for visualizing GNSS data such as skyplot, azimuth-elevation,time-elevation, ground track and band plots. Additionally, this library can be used for basic geodetic computations such as geodetic positions on reference ellipsoid and projection computations.

# How to install?
Download the package and change directory of your terminal to gnsspy-master folder. Then, simply type
```
python setup.py install
```
Or you can directly install package from GitHub via
```
pip install git+https://github.com/GNSSpy-Project/gnsspy
```
# How to use?
A detailed version of manual will be released soon.

## Read RINEX Observation File
`read_obsFile` function reads RINEX 2.x/3.x observation files. If the station is IGS station, RINEX file does not necessarily need to be exist in working directory. In that case, the file is automatically downloaded to working directory. 
```python
import gnsspy as gp
station = gp.read_obsFile("mate2440.17o")
```
`read_obsFile` function returns to a class instance. This instance
```python
# Epoch of RINEX file as datetime
station.epoch
# Pandas.DataFrame of observations
station.observation
# Approximate position [type:list-> x,y,z]
station.approx_position
# Antenna Type
station.antenna_type
# Observation interval(seconds)
station.interval
# Receiver clock error
# (if available)
station.receiver_clock
# Receiver Type
station.receiver_type
# RINEX version
station.version
# RINEX filename
station.filename
```

## Interpolation of SP3 Final Products
`sp3_interp` function interpolates final precise orbit coordinates of satellites at RINEX observation epochs. Default interpolation method is 16 degree polynomial interpolation. Degree of polynomial can be changed, though it is not recommended to use lower than 11 degree. Above 16 degree is not applicable for 15 minute intervals of precise orbit solution. GFZ orbit and clock files are default product names. Alternatives are IGS, WUM, ESA etc. Of course, each product provides solution for different satellite systems, hence number of satellites may vary for each product choice.
```python
orbit = gp.sp3_interp(station.epoch, interval=station.interval, poly_degree=16, sp3_product="gfz", clock_product="gfz")
```
## Single Point Positioning (SPP)
In order to use `spp` function, station file must be read and SP3 interpolation must be done. Satellite system can be chosed via `system` argument as in the example. G: GPS - R: GLONASS - E: GALILEO - C: COMPASS - J: QZSS - I: IRNSS. It should be noted that the choice of station file and products used for the SP3 interpolation can constrain satellite system selection. Additionally, elevation mask angle (cut_off) is by default 7.0 degree. In next release, more options will be added to this function.
```python
spp_result = gp.spp(station, orbit, system="G", cut_off=7.0)
```

# Notes
crx2rnx function is not pure python implementation and depends on 
RNXCMP software for compression/restoration of RINEX observation files 
developed by Y. Hatanaka of GSI.

Source: http://terras.gsi.go.jp/ja/crx2rnx.html

Reference: Hatanaka, Y. (2008): A Compression Format and Tools for GNSS Observation Data, Bulletin of the Geographical Survey  Institute, 55, 21-30, available at http://www.gsi.go.jp/ENGLISH/Bulletin55.html
