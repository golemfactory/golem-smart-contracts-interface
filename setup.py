from setuptools import setup

setup(
    name='Golem-Smart-Contracts-Interface',
    version='1.0.3',
    url='https://github.com/golemfactory/golem-smart-contracts-interface',
    maintainer='The Golem team',
    maintainer_email='tech@golem.network',
    packages=[
        'golem_sci',
        'golem_sci.contracts',
        'golem_sci.contracts.data',
        'golem_sci.contracts.data.rinkeby',
        'golem_sci.contracts.data.mainnet',
    ],
    python_requires='>=3.5',
    install_requires=[
        'ethereum==1.6.1',
        'eth-abi==0.5.0',
        'eth-keyfile==0.4.1',
        'eth-keys==0.1.0b4',
        'eth-utils==0.7.4',
        'eth-tester==0.1.0b15',
        'pytz',
        'rlp==0.6.0',
        'web3==3.16.4',
    ],
)
