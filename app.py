import os

from flask import Flask
from flask import request
from flask import render_template

from tokenbrowser.utils import validate_address, validate_int_string, validate_decimal_string, parse_int
from tokenbrowser.tx import sign_transaction

from decimal import Decimal

from tokenbrowser.ethereum_service_client import EthereumServiceClient

app = Flask(__name__)

ETHEREUM_SERVICE_URL = os.environ['ETHEREUM_SERVICE_URL']
FAUCET_ADDRESS = os.environ['FAUCET_ADDRESS']
FAUCET_PRIVATE_KEY = os.environ['FAUCET_PRIVATE_KEY']

@app.route('/', methods=['GET', 'POST'])
def main():

    client = EthereumServiceClient(ETHEREUM_SERVICE_URL)
    confirmed, unconfirmed = client.get_balance(FAUCET_ADDRESS)

    args = {'faucet_address': FAUCET_ADDRESS, 'available_ethereum': Decimal(unconfirmed) / 10 ** 18}

    if request.method == 'POST':
        print(request.form['address'], request.form['value'])
        if not all(x in request.form for x in ['address', 'value']):
            args['error'] = "Missing required arguments"
        elif not validate_address(request.form['address'].strip()):
            args['error'] = "Invalid Address"
        if not (validate_int_string(request.form['value'].strip()) or validate_decimal_string(request.form['value'].strip())):
            args['error'] = "Invalid Eth amount"
        else:
            address = request.form['address'].strip()
            value = request.form['value'].strip()
            if validate_int_string(value):
                value = parse_int(value)
            else:
                value = Decimal(value)

            wei = int(value * 10 ** 18)

            try:
                tx = client.generate_tx_skel(FAUCET_ADDRESS, address, wei)
                tx_hash = client.send_tx(sign_transaction(tx, FAUCET_PRIVATE_KEY))
                args['tx_hash'] = tx_hash
                args['success'] = True

            except Exception as e:
                args['error'] = str(e)

        args.update({k: request.form[k] for k in request.form.keys()})
    return render_template('index.html', **args)
