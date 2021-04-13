"""
GNSSpy setup file
Mustafa Serkan ISIK and Volkan Ozbey
"""
from setuptools import setup
import re

def get_property(prop, project):
    result = re.search(r'{}\s*=\s*[\'"]([^\'"]*)[\'"]'.format(prop), open(project + '/__init__.py').read())
    return result.group(1)

setup(
  name = 'gnsspy',
  packages = ["gnsspy",
              "gnsspy.io",
              "gnsspy.position",
              "gnsspy.funcs",
              "gnsspy.geodesy",
              "gnsspy.doc"],
  install_requires=[
    "pandas",
    "numpy",
    "matplotlib",
    "pyunpack",
    "hatanaka",
    "tqdm",
  ],
  include_package_data = True,
  package_data = {"gnsspy.doc": ["IGSList.txt"]},
  data_files = [("", ["LICENSE"])],
  version = get_property('__version__', 'gnsspy'),
  description = 'Python Toolkit for GNSS Data',
  author = get_property('__author__', 'gnsspy'),
  author_email = 'isikm@itu.edu.tr - ozbeyv@itu.edu.tr',
  license = 'MIT',
  url = 'https://github.com/GNSSpy-Project/gnsspy',
  download_url = 'https://github.com/GNSSpy-Project/gnsspy/archive/0.1.tar.gz',
  classifiers = [],
  zip_safe=False
)   

