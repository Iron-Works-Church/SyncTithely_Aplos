#!/bin/env python
import requests
import pprint
import datetime
import json
from aplos import *
import boto3

sns = boto3.client('sns')

charge_type = "card"

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

def get_tithely_charges(tithely_org, tithely_user, tithely_pass):
    parameters = {"organization_id": tithely_org, "limit": 100}
    r = requests.get("https://tithe.ly/api/v1/charges-list", params=parameters, auth=(tithely_user, tithely_pass))
    response = r.json()
    return(response)

def convert_timestamp(timestamp1):
   return(datetime.datetime.fromtimestamp(int(timestamp1)).strftime('%Y-%m-%d'))   

def find_latest_deposit(response):
    deposit_date = 0
    for i in response["data"]:
        if i["deposit_date"] != "pending":
                if int(i["deposit_date"]) > int(deposit_date):
                    deposit_date = i["deposit_date"]
    return(deposit_date)

def find_batch_details(response, deposit_date, charge_type):
    gross_amount = 0
    fees = 0
    batch_details = {}
    batch_details["details"] = {}
    batch_details["name"] = "Tithely Deposit for " + charge_type + " " + convert_timestamp(deposit_date)
    batch_details["date"] = convert_timestamp(deposit_date)
    for i in response["data"]:
        if i["deposit_date"] == deposit_date:
            charge_id = i["charge_id"]
            actual_charge_type =get_tithely_method(tithely_org, tithely_user, tithely_pass, charge_id)
            if actual_charge_type == charge_type:
                gross_amount = int(i["amount"]) + gross_amount
                fees = i["fees"] + fees
                fund = i["giving_type"]
                if fund not in batch_details["details"]:
                    batch_details["details"][fund] = {"id": 62, "amount": "0", "fees": "0"}
                batch_details["details"][fund]["amount"] = int(batch_details["details"][fund]["amount"]) + int(i["amount"])
                batch_details["details"][fund]["fees"] = int(batch_details["details"][fund]["fees"]) + int(i["fees"])
    return(batch_details)

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

def convert_cents_dollars_find_total(batch_details):
    batch_details["total"] = 0
    for i, v in batch_details["details"].items():
       v["amount"] = v["amount"] / 100
       v["fees"] = v["fees"] / 100
       batch_details["total"] = v["amount"] + batch_details["total"] + v["fees"]
       batch_details["total"] = round(batch_details["total"], 2)
    return(batch_details)

def add_deposit_aplos(api_base_url, api_id, api_access_token, batch_details):
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

def get_tithely_method(tithely_org, tithely_user, tithely_pass, charge_id):
    parameters = {"organization_id": tithely_org, "limit": 100}
    r = requests.get("https://tithe.ly/api/v1/charges/{}".format(charge_id), auth=(tithely_user, tithely_pass))
    response = r.json()
    return(response["object"]["payment_method"]["pm_type"])

def process_transactions(charge_type, response, deposit_date):
    batch_details = find_batch_details(response, deposit_date, charge_type)
    batch_details = match_funds(api_base_url, api_id, api_access_token, batch_details)
    batch_details = convert_cents_dollars_find_total(batch_details)
    deposit_exists = check_aplos(batch_details)
    if not deposit_exists:
        add_deposit_aplos(api_base_url, api_id, api_access_token, batch_details)
    print(batch_details)


def lambda_handler(event, context):
    # Initial Query

    response = get_tithely_charges(tithely_org, tithely_user, tithely_pass)
    deposit_date = find_latest_deposit(response)

    # Process for Cards

    charge_type = "card"

    process_transactions(charge_type, response, deposit_date)

    # Process for Bank

    charge_type = "bank"

    process_transactions(charge_type, response, deposit_date)
    return {
        'statusCode': 200,
        'body': json.dumps('Completed')
    }



lambda_handler("test", "test")
