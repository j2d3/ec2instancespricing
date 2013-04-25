#!bin/python

dbfile='dbs/aws.db'
org='bhs'
region='us-east-1'
#import modules
import sys
import boto.ec2
import boto.rds
import subprocess
import datetime
from pprint import pprint
import sqlite3 as lite
import json
import argparse

#PARSE CLI ARGS
parser = argparse.ArgumentParser(description='Select certain instances for tagging based on stackname')

parser.add_argument('account', metavar='N', type=str, help='DEV or PROD?')

args = parser.parse_args()

account=args.account

if account == "prod":
  access='AKIAJ3AAQLSORIB3GLPA'
  secret='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'
elif account == "dev":
  access='AKIAIAV7LAX54YREO24Q'
  secret='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'
else:
  quit("no valid account specified")
  
#connect to db
con = lite.connect(dbfile)
with con:
    cur = con.cursor()

#grab instances from DB that match
sql = str("SELECT " +
         "id, name, environment, stackname, role, zone, cost from instances " +
      "WHERE " +
         "account='" + account + "' and " +
         "state='running' " +
      "ORDER BY " +
         "environment, zone")
         
cur.execute(str(sql))
data = cur.fetchall()

#set up opening of doc
json_content='{"name":"' + org
json_content += '","type":"org","children":[\n{"name":"' + account
#we're not looping through accounts just yet, so just do this per-account
json_content += '","type":"account","children":[\n'

environments = {}
stacknames = {}
zones = {}

for line in data:
  
  #collect all envs
  if line[2] not in environments:
    environments[line[2]] = line[2]
    continue
  if line[3] not in stacknames:
    stacknames[line[3]] = line[3]
    continue
  if line[5] not in zones:
    zones[line[5]] = line[5]
    continue
first = True    
for environment in environments:
  if first is False:
    json_content += ','
  first = False
  json_content += '\n'
  json_content += '{"name":"' + str(environment)
  json_content += '","type":"environment","children":[\n'
  first = True
  for line in data:
    
    if line[2] == environment:
      #this instance belongs to this env.
      if first is False:
        json_content += ',\n'
      first = False
      size = int(40000 * float(line[6]))
      json_content += '{"name":"' + str(line[1]) + '","size":"' + str(size) + '"}'
  json_content += '\n]}'
json_content += '\n]}\n]}'
	
print json_content