#!bin/python

#this is responsible for populating the sqlite3 db via queries to AWS
#it is the *only script* in this project that should directly talk to 
#AWS via boto, in order to ensure we don't overload AWS api

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
import time
import socket

#PARSE CLI ARGS
parser = argparse.ArgumentParser(description='Get the state and running cost of AWS EC2 instances in a given account')
parser.add_argument('account', metavar='N', type=str, help='account name')
args = parser.parse_args()
account=args.account

#CONFIG SECTION
dbfile="dbs/aws.db"
region="us-east-1"
platform="linux"
org="bhs"
graphite_server = 'graphite.dev.commandlinesystems.com'
graphite_port = 2003

#full path to dependencies
ec2_instance_pricing="/Users/johndurkin/j2d3/oc3/ec2instancespricing/ec2instancespricing.py"

if account == "prod":
  access='AKIAJ3AAQLSORIB3GLPA'
  secret='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'
elif account == "dev":
  access='AKIAIAV7LAX54YREO24Q'
  secret='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'
else:
  quit("no valid account specified")

#def blocks
def run_command(command):
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b'')

#connect to db
con = lite.connect(dbfile)
with con:
    cur = con.cursor()
    
#use boto to get all ec2 instances
ec2_conn = boto.ec2.connect_to_region(
  region,
  aws_access_key_id=access,
  aws_secret_access_key=secret
)
reservations = ec2_conn.get_all_instances()
ec2_instances = [i for r in reservations for i in r.instances]

#use boto to get all rds instances
rds_conn = boto.rds.connect_to_region(
  region,
  aws_access_key_id=access,
  aws_secret_access_key=secret
)

rds_instances = rds_conn.get_all_dbinstances()
rds_total_cost=0
rds_total_num=0
    
ec2_total_cost=0
nostack=0
total_num=0

# open file for csv output
f = open('www/statusfile'+'_'+account, 'w')
firstline = '{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11}'.format( 
	"id", 
	"name",
	"instance_type", 
	"state", 
	"public_dns_name", 
	"role",
	"stackname",
	"environment", 
	"zone", 
	"service",
	"cost",
        "asgroupname"
)
f.write(firstline+'\n')

for i in ec2_instances:

  stackname = i.tags.get('aws:cloudformation:stack-name')
  asgroupname = i.tags.get('aws:autoscaling:groupName')
  service = i.tags.get('service')
  name = i.tags.get('Name')
  environment = i.tags.get('environment')
  zone = i.placement
  role = i.tags.get('role')
  
# begin cost calc
#   check to see if we already have this instance size price in the db.

  itype = [str(i.instance_type)]
  cur.execute('SELECT Price, Updated FROM EC2_Prices WHERE Name =?', itype) 
  data = cur.fetchone()
#   if we do, fine use that figure  
  if data:
    cost = str(data[0])
#   otherwise, 
  else:
    command = 'python', ec2_instance_pricing, '--type=ondemand', '--filter-region=us-east-1', '--filter-os-type=linux', '--filter-type='+str(i.instance_type), '--format=csv'
    for line in run_command(command):
      print line
      cost_data = line.split(',')
    
    cost = cost_data[3]
    prices = [(str(i.instance_type)),(cost),(datetime.datetime.now()),(region),(platform)]
    cur.execute('INSERT INTO EC2_Prices(Name,Price,Updated,Region,Platform) VALUES(?,?,?,?,?)', prices)
    con.commit()
  
# end cost calc
  
  lineout = '{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11}'.format(
    i.id, 
    name, 
    i.instance_type, 
    i.state, 
    i.public_dns_name, 
    role, 
    stackname, 
    environment, 
    zone, 
    service,
    cost,
    asgroupname
  )
  f.write(lineout+'\n')
  total_num = total_num +1
  
  if stackname is None:
    nostack=nostack + 1


  #save instances' states to db
  instance_data = [
    (str(i.id)),
    (name),
    (str(i.instance_type)),
    (str(i.state)),
    (datetime.datetime.now()),
    (datetime.datetime.now()),
    (region),
    (platform),
    (org),
    (account),
    (environment),
    (zone),
    (role),
    (stackname),
    (service),
    (cost),
    (asgroupname)
  ]
  
  instance_update = [
    (i.tags.get('Name')),
    (str(i.state)),
    (datetime.datetime.now()),
    (str(i.id))
  ]
    
  cur.execute('INSERT OR IGNORE INTO instances(id,name,type,state,created,updated,region,platform,org,account,environment,zone,role,stackname,service,cost,asgroupname) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', instance_data)
  
  con.commit()
  cur.execute('UPDATE instances SET name=?,state=?,updated=? WHERE id=?', instance_update)
  con.commit() 
  
  if str(i.state) == "running":
    print "RUNNING @ $%s/hr" % (cost)
    ec2_total_cost = ec2_total_cost + float(cost)
    
  print "----------------------------------------------------------------------------------------"



rds_total_cost = 0
for i in rds_instances:
  
  rds_total_num = rds_total_num + 1
  print "RDS INSTANCE CLASS: " + str(i.instance_class)
  print "multi_az: " + str(i.multi_az)
  itype = [(str(i.instance_class)),(str(i.multi_az))]
  cur.execute('SELECT Price, Updated FROM RDS_Prices WHERE Class =? AND MultiAZ = ?', itype) 
  data = cur.fetchone()
  platform = "mysql"
  region = "us-east-1"
  
  if data:
    cost = str(data[0])
  else:
    cost = str(raw_input("Please enter price for instance class: " + str(i.instance_class) + " multiaz: " + str(i.multi_az) + ":\n"))
    name = str(i.instance_class) + ":" + str(i.multi_az)
    prices = [(name),(str(i.instance_class)),(str(i.multi_az)),(cost),(datetime.datetime.now()),(region),(platform)]
    cur.execute('INSERT INTO RDS_Prices(Name,Class,MultiAZ,Price,Updated,Region,Platform) VALUES(?,?,?,?,?,?,?)', prices)
    con.commit()
  
  rds_total_cost = rds_total_cost + float(cost)


print "%s RUNNING INSTANCES" % (total_num) 
print "NOSTACK: " + str(nostack)
print "TOTAL EC2 COST: $%s/hr" % (ec2_total_cost)  
print "%s RUNNING RDS INSTANCES" % (rds_total_num)  
print "TOTAL RDS COST: $%s/hr" % (rds_total_cost) 

print "GRAND TOTAL HOURLY EC2 + RDS: $%s/hr" % (ec2_total_cost + rds_total_cost)

ftot = open('www/totalsfile'+'_'+account, 'w')
totals_keys = '{0},{1},{2},{3},{4}'.format( 
	"ec2_num", 
	"ec2_cost",
	"rds_num", 
	"rds_cost",
	"total"
)
totals_vals = '{0},{1},{2},{3},{4}'.format( 
	(total_num), 
	(ec2_total_cost),
	(rds_total_num), 
	(rds_total_cost),
	(ec2_total_cost + rds_total_cost)
)
ftot.write(totals_keys+'\n'+totals_vals+'\n')

timestamp = int(time.time())
ec2_message = '%s %s %d\n' % ("cost." + account + ".ec2", ec2_total_cost, timestamp)
rds_message = '%s %s %d\n' % ("cost." + account + ".rds", rds_total_cost, timestamp)

sock = socket.socket()
sock.connect((graphite_server, graphite_port))
sock.sendall(ec2_message)
sock.sendall(rds_message)
sock.close()





