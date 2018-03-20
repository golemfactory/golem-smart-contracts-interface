import json
import click

TESTNET_CONTRACTS = [
    'GolemNetworkToken',
    'GolemNetworkTokenBatching',
    'GNTPaymentChannels',
    'GNTDeposit',
    'Faucet',
]

MAINNET_CONTRACTS = [
    'GolemNetworkTokenBatching',
]

TEMPLATE = "\
ADDRESS = ''\n\
ABI = '{}'  # noqa\n\
BIN = '{}'  # noqa\n\
"


@click.command()
@click.option(
    "--filename",
    required=True,
    help="JSON file generated using `solc contracts/* --combined-json abi,bin`")
@click.option(
    "--output_dir",
    help="Where to save output (or stdout if not provided)")
@click.option(
    "--mainnet",
    is_flag=True,
    default=False,
    help="Mainnet if provided, rinkeby otherwise")
def main(filename, output_dir, mainnet):
    with open(filename, 'r') as f:
        data = json.load(f)
    contracts = {
        key.split('/')[-1]: value for key, value in data['contracts'].items()
    }
    contract_names = MAINNET_CONTRACTS if mainnet else TESTNET_CONTRACTS
    for contract_name in contract_names:
        contract = contracts['{0}.sol:{0}'.format(contract_name)]
        content = TEMPLATE.format(
            contract['abi'],
            contract['bin'],
        )
        if output_dir:
            output_filepath = '{}/{}.py'.format(
                output_dir,
                contract_name.lower(),
            )
            with open(output_filepath, 'w+') as f:
                f.write(content)
        else:
            print(content)


if __name__ == "__main__":
    main()
