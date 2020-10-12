#!/bin/env python
import base64
import json
import os
import textwrap
import subprocess
import sys

try:
    from requests import requests
except:
    import requests

try:
    from rsa import rsa
except:
    import rsa

api_base_url = 'https://www.aplos.com/hermes/api/v1/'


with open("creds.json", encoding='utf-8') as f:
    credentials = json.load(f)
    api_id = credentials["aplos_api_id"]


with open(api_id + '.key', mode='rb') as pkeyfile:
    api_user_pemkey = pkeyfile.read()
    api_user_key = rsa.PrivateKey.load_pkcs1(api_user_pemkey)

def api_auth(api_base_url, api_id, api_user_key):
    # This should return an authorized token so we can do other, more exciting things
    # Lets show what we're doing.
    print('geting URL: {}auth/{}'.format(api_base_url, api_id))

    # Actual request goes here.
    r = requests.get('{}auth/{}'.format(api_base_url, api_id))
    data = r.json()
    api_error_handling(r.status_code)

    api_token_encrypted = data['data']['token']
    api_token_encrypted_expires = data['data']['expires']
    print('The API Token expires: {}'.format(api_token_encrypted_expires))
    #print(api_token_encrypted)

    api_bearer_token = rsa.decrypt(
    base64.b64decode(api_token_encrypted), api_user_key)
    api_bearer_token = api_bearer_token.decode("utf-8")
    return(api_bearer_token)


def api_error_handling(status_code):
    # Some Basic Error Handling:
    # Check for HTTP codes other than 200
    if status_code != 200:
        if status_code == 401:
            print('Status:', status_code, 'Something is wrong with the auth code. Exiting')
            exit()
        elif status_code == 403:
            print('Status:', status_code, 'Forbidden. Exiting')
            exit()
        elif status_code == 405:
            print('Status:', status_code, 'Method not allowed. Exiting')
            exit()
        elif status_code == 422:
            print('Status:', status_code, 'Unprocessable Entity. Exiting')
            exit()
        print('Status:', status_code, 'Problem with the request. Exiting.')
        exit()
    else:
        print('Status:', status_code, ': The API let me in!')
    return()

def api_transactions_get(api_base_url, api_id, api_access_token, parameters):
    # This should print a contact from Aplos.
    # Lets show what we're doing.
    headers = {'Authorization': 'Bearer: {}'.format(api_access_token)}
    print('geting URL: {}transactions'.format(api_base_url))
    print('With headers: {}'.format(headers))

    # Actual request goes here.
    #parameters ={'f_rangestart': '2020-10-08', 'f_rangeend': '2020-10-08',}
    r = requests.get('{}./transactions'.format(api_base_url), headers=headers, params=parameters)
    api_error_handling(r.status_code)
    response = r.json()

    #print('JSON response: {}'.format(response))
    #print(response)
    return (response)



api_access_token = api_auth(api_base_url, api_id, api_user_key)

