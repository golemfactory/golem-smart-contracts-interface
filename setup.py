#!/usr/bin/env python3
import pathlib

from setuptools import setup

try:
    from version import get_version
except ImportError:
    def get_version(cwd, **_kwargs):
        p = pathlib.Path(cwd) / 'RELEASE-VERSION'
        with p.open('r') as f:
            return f.read()

version_cwd = str(pathlib.Path(__file__).parent / 'golem_sci')


setup(
    name='Golem-Smart-Contracts-Interface',
    version=get_version(prefix='v', cwd=version_cwd),
    url='https://github.com/golemfactory/golem-smart-contracts-interface',
    maintainer='The Golem team',
    maintainer_email='tech@golem.network',
    packages=[
        'golem_sci',
    ],
    python_requires='>=3.6',
    install_requires=[
        'ethereum==1.6.1',
        'eth-abi==1.1.1',
        'eth-keyfile==0.5.1',
        'eth-keys==0.2.0b3',
        'eth-utils==1.0.3',
        'pytz',
        'rlp==0.6.0',
        'web3==4.2.1',
    ],
)
