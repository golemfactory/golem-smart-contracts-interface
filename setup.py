from setuptools import setup

setup(
    name='Golem-Smart-Contracts-Interface',
    version='1.10.1',
    url='https://github.com/golemfactory/golem-smart-contracts-interface',
    maintainer='The Golem team',
    maintainer_email='tech@golem.network',
    packages=[
        'golem_sci',
    ],
    python_requires='>=3.6',
    install_requires=[
        'ethereum==1.6.1',
        'eth-abi==1.2.0',
        'eth-keyfile==0.5.1',
        'eth-keys==0.2.0b3',
        'eth-utils==1.2.0',
        'pytz',
        'rlp==0.6.0',
        'web3==4.9.2',
    ],
)
