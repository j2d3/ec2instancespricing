#!bin/python

dbfile='dbs/aws.db'
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
parser.add_argument('like', metavar='N', type=str, help='stackname is LIKE?')
parser.add_argument('env', metavar='N', type=str, help='environment to apply')
args = parser.parse_args()

account=args.account
like=args.like
env=args.env

if account == "prod":
  access='AKIAJ3AAQLSORIB3GLPA'
  secret='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'
elif account == "dev":
  access='AKIAIAV7LAX54YREO24Q'
  secret='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'
else:
  quit("no valid account specified")
  
#establish a connection to ec2 aws api with boto
ec2_conn = boto.ec2.connect_to_region(
  region,
  aws_access_key_id=access,
  aws_secret_access_key=secret
)

#connect to db
con = lite.connect(dbfile)
with con:
    cur = con.cursor()

#grab instances from DB that match
cur.execute(str("select id, environment, name, stackname from instances where stackname LIKE '%" + like + "%' and state='running'"))
data = cur.fetchall()


for instance in data:
  filter = "filters={" + instance[0] + "}"
  reservations = ec2_conn.get_all_instances(instance[0])
  i = reservations[0].instances[0]
  print "name: " + instance[2]
  print "stackname: " + instance[3]
  if i.tags.has_key("Name"):
    if str(i.tags["Name"]).find(like) or instance[3].find(like):
      print "stackname or env like target"
      if i.tags.has_key("environment"):
        print i.tags["environment"] + " and " + env
        if i.tags["environment"] == env:
          print "they match"
        else: 
          print "resetting env"
          i.remove_tag(i.tags["environment"])
          ec2_conn.create_tags([i.id], { "environment": env })  
      else:
        print "needs environment tag"
        ec2_conn.create_tags([i.id], { "environment": env })
  else:
    print "NO NAME"

  print "######################"             
  
  


