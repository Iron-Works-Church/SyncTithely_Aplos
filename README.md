# SyncTithely_Aplos
Simple program to send latest Tithely Deposit(s) to Aplos.

The program looks for the most recent deposit date and will create deposit entries in Aplos for the tithely deposits, classifying / splitting them out according to the "giving_type" field in Tithely.  This must match the Aplos fund id or an error will be thrown.  The code is designed to run on AWS Lambda with SNS to notify staff of errors.  Create your own creds.json file with with credentials and url's for your environment.   Some other information must be set as well (such as aplos account #'s for tithely fees).
