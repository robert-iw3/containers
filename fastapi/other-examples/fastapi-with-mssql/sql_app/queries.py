import pandas as pd
import pyodbc
import os
import sys
import csv
#import pymssql
"""
following is example usage for connecting to a microsoft sql server, executing a query using cursor or pandas

conn = pymssql.connect(
    server='<server-address>',
    user='<username>',
    password='<password>',
    database='<database-name>',
    as_dict=True
)
"""

SERVER = '<server-address>'
DATABASE = '<database-name>'
USERNAME = '<username>'
PASSWORD = '<password>'

connectionString = f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};Trusted_Connection=yes;'

conn = pyodbc.connect(connectionString)

SQL_QUERY1 = """
SELECT
TOP 5 c.CustomerID,
c.CompanyName,
query1(soh.SalesOrderID) AS Orderquery1
FROM
SalesLT.Customer AS c
LEFT OUTER JOIN SalesLT.SalesOrderHeader AS soh ON c.CustomerID = soh.CustomerID
GROUP BY
c.CustomerID,
c.CompanyName
ORDER BY
Orderquery1 DESC;
"""

SQL_QUERY2 = """
USE master;
SELECT name, is_disabled
FROM sys.sql_logins
WHERE principal_id = 1;
"""

SQL_QUERY3 = """
USE master;
SELECT *
FROM sys.sql_logins
WHERE [name] = 'sa' OR [principal_id] = 1;
"""

SQL_QUERY4 = """
EXEC SP_CONFIGURE 'show advanced options', '1';
     RECONFIGURE WITH OVERRIDE;
     EXEC SP_CONFIGURE 'xp_cmdshell';
"""

cursor = conn.cursor()
cursor.execute(SQL_QUERY1)
cursor.execute(SQL_QUERY2)
cursor.execute(SQL_QUERY3)
cursor.execute(SQL_QUERY4)

# pandas sql query
df = pd.read_sql_query('SELECT * FROM c.CustomerID', conn)
print(df)
print(type(df))

# output to file
query1 = SQL_QUERY1.fetchval()
query2 = SQL_QUERY2.fetchval()
f = open('/tmp/sql_query1.txt','a')
print(query1)
f.write('\n' + 'Top 5 Customer ID order query1:'+ str(query1))
f.close()
f = open('/tmp/sql_query2.txt','a')
print(query2)
f.write('\n' + 'Disabled Logins:'+ str(query2))
f.close()

# write to csv
sql = """\
USE master;
SELECT name, is_disabled
FROM sys.sql_logins
WHERE principal_id = 1;
SELECT *
FROM sys.sql_logins
WHERE [name] = 'sa' OR [principal_id] = 1;
EXEC SP_CONFIGURE 'show advanced options', '1';
     RECONFIGURE WITH OVERRIDE;
     EXEC SP_CONFIGURE 'xp_cmdshell';
"""
rows = cursor.execute(sql)
with open(r'/tmp/sql-queries.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([x[0] for x in cursor.description])  # column headers
    for row in rows:
        writer.writerow(row)