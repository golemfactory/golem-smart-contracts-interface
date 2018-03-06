import json
import click

CONTRACTS = [
    'GolemNetworkToken',
    'GolemNetworkTokenBatching',
    'GNTPaymentChannels',
    'GNTDeposit',
    'Faucet',
]

TEMPLATE = "\
class {}:\n\
    ADDRESS = ''\n\
    ABI = '{}'  # noqa\n\
    BIN = '{}'  # noqa\n\
"


@click.command()
@click.option(
    "--filename",
    help="JSON file generated using `solc contracts/* --combined-json abi,bin`")
@click.option(
    "--output_dir",
    help="Where to save output (or stdout if not provided)")
def main(filename, output_dir):
    with open(filename, 'r') as f:
        data = json.load(f)
    contracts = {
        key.split('/')[-1]: value for key, value in data['contracts'].items()
    }
    for contract_name in CONTRACTS:
        contract = contracts['{0}.sol:{0}'.format(contract_name)]
        content = TEMPLATE.format(
            contract_name,
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
