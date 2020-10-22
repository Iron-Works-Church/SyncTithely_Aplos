#!/bin/env python
import requests
import pprint
import datetime
import json
from aplos import *
import boto3

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
    #pprint.pprint(response)
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
                if i["charge_status"] == "charged":
                    batch_details["details"][fund]["amount"] = int(batch_details["details"][fund]["amount"]) + int(i["amount"])
                    batch_details["details"][fund]["fees"] = int(batch_details["details"][fund]["fees"]) + int(i["fees"])
    return(batch_details)

def convert_cents_dollars_find_total(batch_details):
    batch_details["total"] = 0
    for i, v in batch_details["details"].items():
       v["amount"] = int(v["amount"]) / 100
       v["fees"] = int(v["fees"]) / 100
       batch_details["total"] = v["amount"] + batch_details["total"] + v["fees"]
       batch_details["total"] = round(batch_details["total"], 2)
    return(batch_details)

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
    #pprint.pprint(batch_details)
    if not deposit_exists:
        add_deposit_aplos(api_base_url, api_id, api_access_token, batch_details, church_name)
        create_cp_xfer_expense(api_base_url, api_id, api_access_token, batch_details, church_name)
        create_cp_xfer_deposit(api_base_url, api_id, api_access_token, batch_details, church_name)

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


lambda_handler("event", "context")