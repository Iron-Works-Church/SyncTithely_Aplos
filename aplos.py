#!/bin/env python
import base64
import json
import os
import textwrap
import subprocess
import sys
import boto3
import pprint

try:
    from requests import requests
except:
    import requests

try:
    from rsa import rsa
except:
    import rsa

api_base_url = 'https://www.aplos.com/hermes/api/v1/'

sns = boto3.client('sns')

with open("creds.json", encoding='utf-8') as f:
    credentials = json.load(f)
    sc_user = credentials["sc_user"]
    sc_pass = credentials["sc_pass"]
    sc_baseurl = credentials["sc_baseurl"]
    s3_bucket = credentials["s3_bucket"]
    sns_topic = credentials["sns_topic"]
    api_id = credentials["aplos_api_id"]
    api_base_url = credentials["api_base_url"]
    tithely_user = credentials["tithely_user"]
    tithely_pass = credentials["tithely_pass"]
    tithely_org = credentials["tithely_org"]
    church_name = credentials["church_name"]


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

def add_deposit_aplos(api_base_url, api_id, api_access_token, batch_details, church_name):
    headers = {'Authorization': 'Bearer: {}'.format(api_access_token)}
    print('Posting URL: {}transactions'.format(api_base_url))
    print('With headers: {}'.format(headers))
    line_num = 0
    payload = {
  "note": batch_details["name"],
  "date": batch_details["date"],
  "contact": {
     "companyname": church_name,
     "type": "company"
    },
    "lines": []
    }
    for k, v in batch_details["details"].items():
        payload["lines"].append({"amount": v["amount"], "account": {"account_number": 1000}, "fund": {"id": v["id"]}})
        payload["lines"].append({"amount": 0 - v["amount"], "account": {"account_number": 4002}, "fund": {"id": v["id"]}})
        payload["lines"].append({"amount": v["fees"], "account": {"account_number": 5003}, "fund": {"id": v["id"]}})
        payload["lines"].append({"amount": 0 - v["fees"], "account": {"account_number": 1000}, "fund": {"id": v["id"]}})
    jsonData = json.dumps(payload)
    r = requests.post(
        '{}transactions'.format(api_base_url), headers=headers, data=jsonData)
    api_error_handling(r.status_code)
    response = r.json()
    sns.publish(TopicArn=sns_topic, Message=('JSON response: {}'.format(response)))

def create_cp_xfer_expense(api_base_url, api_id, api_access_token, batch_details, church_name):
    headers = {'Authorization': 'Bearer: {}'.format(api_access_token)}
    print('Posting URL: {}transactions'.format(api_base_url))
    print('With headers: {}'.format(headers))
    line_num = 0
    payload = {
  "note": "Church Planting Transfer from General (Automated)",
  "date": batch_details["date"],
  "contact": {
     "companyname": church_name,
     "type": "company"
    },
    "lines": []
    }
    for k, v in batch_details["details"].items():
        if v["id"] == 48655:
            xfer_amount = v["amount"] / 10
            xfer_amount = round(xfer_amount, 2)
            payload["lines"].append({"amount": xfer_amount, "account": {"account_number": 16000}, "fund": {"id": v["id"]}})
            payload["lines"].append({"amount": 0 - xfer_amount, "account": {"account_number": 1000}, "fund": {"id": v["id"]}})
         
    jsonData = json.dumps(payload)
    r = requests.post(
        '{}transactions'.format(api_base_url), headers=headers, data=jsonData)
    api_error_handling(r.status_code)
    response = r.json()
    sns.publish(TopicArn=sns_topic, Message=('JSON response: {}'.format(response)))

def create_cp_xfer_deposit(api_base_url, api_id, api_access_token, batch_details, church_name):
    headers = {'Authorization': 'Bearer: {}'.format(api_access_token)}
    print('Posting URL: {}transactions'.format(api_base_url))
    print('With headers: {}'.format(headers))
    line_num = 0
    payload = {
  "note": "Church Planting Deposit to CP Fund (Automated)",
  "date": batch_details["date"],
  "contact": {
     "companyname": church_name,
     "type": "company"
    },
    "lines": []
    }
    for k, v in batch_details["details"].items():
        xfer_amount = v["amount"] / 10
        xfer_amount = round(xfer_amount, 2)
        #only transfer money for that received in general fund - note that funds are different for the deposit side
        if v["id"] == 48655:
            payload["lines"].append({"amount": xfer_amount, "account": {"account_number": 1000}, "fund": {"id": 50194}})
            payload["lines"].append({"amount": 0 - xfer_amount, "account": {"account_number": 4251}, "fund": {"id": 50194}})
         
    jsonData = json.dumps(payload)
    r = requests.post(
        '{}transactions'.format(api_base_url), headers=headers, data=jsonData)
    api_error_handling(r.status_code)
    response = r.json()
    sns.publish(TopicArn=sns_topic, Message=('JSON response: {}'.format(response)))

def check_aplos(batch_details):
    params = {}
    params["f_rangestart"] = batch_details["date"]
    params["f_rangeend"] = batch_details["date"]
    aplos_transactions = api_transactions_get(api_base_url, api_id, api_access_token, params)
    deposit_exists = False
    for i in aplos_transactions["data"]["transactions"]:
        if i["note"] == batch_details["name"] and "${:,.2f}".format(i["amount"]) == "${:,.2f}".format(float(batch_details["total"])):
            deposit_exists = True
    if deposit_exists:
        print("Deposit Exists - No action Taken")
    else:
        print("Making new Deposit")
    return(deposit_exists)

def match_funds(api_base_url, api_id, api_access_token, batch_details):
    headers = {'Authorization': 'Bearer: {}'.format(api_access_token)}
    print('geting URL: {}funds'.format(api_base_url))
    print('With headers: {}'.format(headers))
    r = requests.get('{}funds'.format(api_base_url), headers=headers)
    api_error_handling(r.status_code) 
    response1 = {}
    response1 = r.json()
    for i, v in batch_details["details"].items():
        for i2 in response1["data"]["funds"]:
            if i == i2["name"]:
                v["id"] = i2["id"]
        if v["id"] == 62:
            sns.publish(TopicArn=sns_topic, Message="fund " + i + " does not match anything in aplos")
            quit()
    return(batch_details)

api_access_token = api_auth(api_base_url, api_id, api_user_key)

