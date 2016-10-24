# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))


class PyTest(TestCommand):
    # Class taken from KeepSafe/aiohttp's setup.py

    def run(self):
        import subprocess
        import sys
        errno = subprocess.call([sys.executable, '-m', 'pytest', 'tests'])
        raise SystemExit(errno)


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

    install_requires=['uvloop', 'aiohttp', 'requests',
                      'pygit2', 'github3.py', 'pyyaml',
                      'coloredlogs'],
    extras_require={
        'test': ['pytest'],
    },
    package_data={
    },
    data_files=[],
    cmdclass={'test': PyTest},
)
