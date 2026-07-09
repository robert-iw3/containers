import os
import pyodbc
#import urllib
#from sqlalchemy import create_engine
#from sqlalchemy import text

SERVER = '<server-address>'
DATABASE = '<database-name>'
USERNAME = '<username>'
PASSWORD = '<password>'

connectionString = f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};Trusted_Connection=yes;'

conn = pyodbc.connect(connectionString)

#params = urllib.parse.quote_plus("DRIVER={ODBC Driver 18 for SQL Server};"
#                                 "SERVER={SERVER};"
#                                 "DATABASE={DATABASE};"
#                                 "UID={USERNAME};"
#                                 "PWD={PASSWORD}")

#engine = create_engine("mssql+pyodbc:///?odbc_connect={}".format(params))

#engine = create_engine('mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}', echo=True)

#with engine.connect() as con:
#    with open("/tmp/sql/myquery.sql") as file:
#        query = text(file.read())
#        con.execute(query)

# place sql file in this directory or change directory
inputdir = 'C:\Users\Public\sqlaudit'

for script in os.listdir(inputdir):
    with open(inputdir+'\\' + script,'r') as inserts:
        sqlScript = inserts.read()
        for statement in sqlScript.split(';'):
            with conn.cursor() as cur:
                cur.execute(statement)
    print(script)

conn.close()