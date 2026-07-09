#!/bin/bash
set -e
export HBASE_HOME=/opt/hbase
export HBASE_OPTS="-Djava.net.preferIPv4Stack=true -Dhbase.manages.zookeeper=false"
export HBASE_MASTER_OPTS="$HBASE_OPTS"
export HBASE_REGIONSERVER_OPTS="$HBASE_OPTS"
# Use the standalone ZooKeeper started above; do not start an embedded one

# Ensure HBase logs directory exists
mkdir -p $HBASE_HOME/logs
chown -R root:root $HBASE_HOME/logs

# 2) Storage HBase
mkdir -p /opt/hbase-data

# 3) ZooKeeper stand-alone di HBase
$HBASE_HOME/bin/hbase-daemon.sh start zookeeper
echo "[INFO] HBase ZooKeeper started"
sleep 5

# 4) Master + RegionServer
$HBASE_HOME/bin/hbase-daemon.sh start master
$HBASE_HOME/bin/hbase-daemon.sh start regionserver
echo "[INFO] HBase Master and RegionServer started"
sleep 10

$HBASE_HOME/bin/hbase-daemon.sh start thrift
echo "[INFO] HBase Thrift Server on port 9090"

tail -f $HBASE_HOME/logs/hbase--master-*.out