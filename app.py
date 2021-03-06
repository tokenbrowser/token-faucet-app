import os
import binascii
import logging
import random
import requests

from flask import Flask
from flask import request
from flask import render_template
from flask import redirect

from toshi.utils import validate_address, validate_int_string, validate_hex_string, validate_decimal_string, parse_int
from toshi.ethereum.tx import sign_transaction

from decimal import Decimal

from toshi.ethereum.utils import sha3, data_decoder, data_encoder
from toshi.clients import EthereumServiceClient

logging.basicConfig()
log = logging.getLogger("log")

app = Flask(__name__)

ETHEREUM_SERVICE_URL = os.environ['ETHEREUM_SERVICE_URL']
FAUCET_ADDRESS = os.environ['FAUCET_ADDRESS']
FAUCET_PRIVATE_KEY = os.environ['FAUCET_PRIVATE_KEY']
UPORT_ID_FACTORY_ADDRESS = os.environ.get('UPORT_ID_FACTORY_ADDRESS', None)
JSONRPC_SERVER = os.environ.get('JSONRPC_SERVER', None)

TOKENS = os.environ.get('TOKENS', [])
if TOKENS:
    TOKENS = [{"address": t.split(',')[0], "symbol": t.split(',')[1], "name": t.split(',')[2], "decimals": int(t.split(',')[3])} for t in TOKENS.split(";")]

def process_tx_args():
    tx_args = {}
    if 'startgas' in request.form:
        startgas = request.form['startgas'].strip()
        if startgas:
            startgas = parse_int(startgas)
            if startgas:
                tx_args['gas'] = startgas
            else:
                raise Exception("Invalid value for startgas")
    if 'gasprice' in request.form:
        gasprice = request.form['gasprice'].strip()
        if gasprice:
            if validate_decimal_string(gasprice):
                gasprice = None
            else:
                gasprice = parse_int(gasprice)
            if gasprice:
                tx_args['gas_price'] = gasprice
            else:
                raise Exception("Invalid value for gasprice")
    return tx_args

@app.route('/', methods=['GET', 'POST'])
def main():

    client = EthereumServiceClient(ETHEREUM_SERVICE_URL)
    confirmed, unconfirmed = client.get_balance(FAUCET_ADDRESS)

    support_uport = UPORT_ID_FACTORY_ADDRESS is not None
    args = {'faucet_address': FAUCET_ADDRESS,
            'available_ethereum': Decimal(unconfirmed) / 10 ** 18,
            'support_uport': support_uport,
            'tokens': TOKENS}

    if request.method == 'POST':
        print(request.form)
        if 'uport' in request.form and support_uport:
            if not all(x in request.form for x in ['address']):
                args['error'] = "Missing required arguments"
            else:

                try:
                    tx_args = process_tx_args()
                    func = sha3('CreateProxyWithControllerAndRecovery(address,address[],uint256,uint256)')[:4]
                    device_addr = data_decoder(request.form['address'].strip()).rjust(32, b'\x00')
                    offset = b'\x80'.rjust(32, b'\x00')  # offset of address[] data
                    longtimeval = b'\x3c'.rjust(32, b'\x00')
                    shorttimeval = b''.rjust(32, b'\x00')
                    delegate_data = b''.rjust(32, b'\x00')
                    data = func + device_addr + offset + longtimeval + shorttimeval + delegate_data
                    tx_args['data'] = data_encoder(data)

                    tx = client.generate_tx_skel(FAUCET_ADDRESS, UPORT_ID_FACTORY_ADDRESS, 0, **tx_args)
                    tx_hash = client.send_tx(sign_transaction(tx, FAUCET_PRIVATE_KEY))
                    args['tx_hash'] = tx_hash
                    args['success'] = True
                    args['uport'] = True

                except binascii.Error:
                    args['error'] = "Invalid address"
                except Exception as e:
                    log.exception("Unexpected exception")
                    args['error'] = str(e)
        else:
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
                    wei = int(value * 10 ** 18)
                elif validate_hex_string(value):
                    wei = parse_int(value)
                else:
                    value = Decimal(value)
                    wei = int(value * 10 ** 18)

                if 'send_token' in request.form:
                    tx_args = process_tx_args()
                    token_to_send = [t for t in TOKENS if request.form['send_token'] == t['symbol']]
                    if len(token_to_send) == 0:
                        args['error'] = "Unknown token address"
                    else:
                        token_to_send = token_to_send[0]
                        token_address = token_to_send['address']
                        value = int(value * 10 ** token_to_send['decimals'])
                        tx_args['data'] = "0xa9059cbb000000000000000000000000{}{:064x}".format(address[2:].lower(), value)
                        args['token'] = token_to_send
                        try:
                            tx = client.generate_tx_skel(FAUCET_ADDRESS, token_address, 0, **tx_args)
                            tx_hash = client.send_tx(sign_transaction(tx, FAUCET_PRIVATE_KEY))
                            args['tx_hash'] = tx_hash
                            args['success'] = True
                        except Exception as e:
                            args['error'] = str(e)
                else:
                    try:
                        tx_args = process_tx_args()
                        tx = client.generate_tx_skel(FAUCET_ADDRESS, address, wei, **tx_args)
                        tx_hash = client.send_tx(sign_transaction(tx, FAUCET_PRIVATE_KEY))
                        args['tx_hash'] = tx_hash
                        args['success'] = True

                    except Exception as e:
                        args['error'] = str(e)

            args.update({k: request.form[k] for k in request.form.keys()})

    elif request.method == 'GET':

        args['address'] = request.args.get('address', '')
        value = request.args.get('wei')
        if value:
            value = parse_int(value)
            if value is None:
                args['error'] = "Invalid 'wei' value"
            else:
                value = str(value)
                if len(value) < 19:
                    value = value.zfill(19)
                value = "{}.{}".format(value[:-18], value[-18:])
                args['value'] = value
        else:
            value = request.args.get('ether')
            if value:
                if value.startswith('0x'):
                    args['error'] = "Hex not allowed in 'ether' arg: use 'wei' instead"
                else:
                    try:
                        value = Decimal(value)
                        args['value'] = value
                    except:
                        args['error'] = "Invalid 'ether' value"

    return render_template('index.html', **args)

@app.route('/tx/<hash>', methods=['GET'])
def get_tx(hash):

    if JSONRPC_SERVER is None:
        return redirect("https://testnet.etherscan.io/tx/{}".format(hash))

    data = {
        "jsonrpc": "2.0",
        "id": random.randint(0, 1000000),
        "method": "eth_getTransactionByHash",
        "params": [hash]
    }
    resp = requests.post(JSONRPC_SERVER, json=data)
    if resp.status_code != 200:
        return render_template('tx.html', error="Unexpected Error")
    resp = resp.json()

    if 'error' in resp:
        return render_template('tx.html', error="Unexpected Error")

    return render_template('tx.html', tx=resp['result'])
