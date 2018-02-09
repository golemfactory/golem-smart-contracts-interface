from setuptools import setup

setup(
    name='Golem-Smart-Contracts-Interface',
    version='0.1.0',
    url='https://github.com/golemfactory/golem-smart-contracts-interface',
    maintainer='The Golem team',
    maintainer_email='tech@golem.network',
    packages=[
        'golem_sci',
    ],
    python_requires='>=3.5',
    install_requires=[
        'ethereum==1.6.1',
        'ethereum-utils==0.5.1',
        'pytz',
        'web3==3.8.0',
    ],
    tests_require=[
        'mock',
    ],
)
