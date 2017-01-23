# Running webapp (locally)

## Setup Env

```
python3 -m virtualenv env
env/bin/pip install -r requirements.txt
```

## Running

```
export ETHERUM_SERVICE_URL=https://token-eth-service.herokuapp.com
export FAUCET_ADDRESS=0x....
export FAUCET_PRIVATE_KEY=0x....
env/bin/flask run --host=0.0.0.0 --port=4000
```

# Running on heroku

```
heroku buildpacks:add https://github.com/debitoor/ssh-private-key-buildpack.git
heroku buildpacks:add heroku/python

heroku config:set SSH_KEY=$(cat path/to/your/keys/id_rsa | base64)
heroku config:set ETHEREUM_SERVICE_URL=https://token-eth-service.herokuapp.com
heroku config:set FAUCET_ADDRESS=0x....
heroku config:set FAUCET_PRIVATE_KEY=0x...

git push heroku master
heroku ps:scale web:1
```
