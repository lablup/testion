# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='testion',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.1.0',
    description='Testion',
    long_description='',
    url='https://github.com/lablup/testion',
    author='Lablup Inc.',
    author_email='joongi@lablup.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Pre-Alpha',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: No Input/Output (Daemon)',
        'Topic :: Software Development :: Testing',
    ],

    packages=['testion'],

    install_requires=['uvloop', 'aiohttp', 'requests', 'github3.py'],
    extras_require={
        'dev': [],
        'test': [],
    },
    package_data={
    },
    data_files=[],
)
