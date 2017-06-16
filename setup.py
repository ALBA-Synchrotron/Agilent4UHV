#!/usr/bin/env python
# Always prefer setuptools over distutils
from setuptools import setup, find_packages

DS = 'Agilent4UHV'
author = 'srubio@cells.es'
version = '4.5.0'
package = 'tangods-'+DS.lower()

url = 'https://git.cells.es/controls/Agilent4UHV'
description = '%s Tango Device Server'%DS
long_description = """
Agilent4UHV controller will replace
the Varian DUAL Ion Pump Controller."""

__doc__ = """
Generic Device Server setup.py file copied from fandango/scripts/setup.ds.py

To install as system package:

  python setup.py install
  
To build src package:

  python setup.py sdist
  
To install as local package, just run:

  mkdir /tmp/builds/
  python setup.py install --root=/tmp/builds
  /tmp/builds/usr/bin/$DS -? -v4

To tune some options:

  RU=/opt/control
  python setup.py egg_info --egg-base=tmp install --root=$RU/files --no-compile \
    --install-lib=lib/python/site-packages --install-scripts=ds

-------------------------------------------------------------------------------
"""

print(__doc__)

license = 'GPL-3.0'
install_requires = ['fandango',
                    'PyTango',]

## All the following defines are OPTIONAL

## For setup.py located in root folder or submodules
package_dir = {
    DS: '.',
    #'DS/tools': './tools',
}
packages = package_dir.keys()

## Additional files, remember to edit MANIFEST.in to include them in sdist
package_data = {'': [
  #'VERSION',
  #'./tools/icon/*',
  #'./tools/*ui',
]}

## Launcher scripts
scripts = [
  DS,
  #'./bin/'+DS,
  ]

## This option relays on DS.py having a main() method
entry_points = {
        #'console_scripts': [
            #'%s = %s.%s:main'%(DS,DS,DS),
        #],
}

setup(
    name=package,
    author=author,
    author_email=author,
    maintainer=author,
    maintainer_email=author,
    url=url,
    download_url=url,
    version=version,
    license=license,
    description=description,
    install_requires=install_requires,    
    packages = packages or find_packages(),
    package_dir= package_dir,
    entry_points=entry_points,    
    scripts = scripts,
    include_package_data = True,
    package_data = package_data    
)
