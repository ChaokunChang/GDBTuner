#!/usr/bin/env bash

script_path="/usr/share/sysbench/"

if [ "${1}" == "read" ]
then
    run_script=${script_path}"oltp_read_only.lua"
elif [ "${1}" == "write" ]
then
    run_script=${script_path}"oltp_write_only.lua"
else
    run_script=${script_path}"oltp_read_write.lua"
fi
# the user here is root, while i don't know why.
sysbench ${run_script} \
        --mysql-host=$2 \
	--mysql-port=$3 \
	--mysql-user=$4 \
	--mysql-password=$5 \
	--mysql-db=sbtest \
	--db-driver=mysql \
        --mysql-storage-engine=innodb \
        --range-size=100 \
        --events=0 \
        --rand-type=uniform \
	--tables=200 \
	--table-size=10000000 \
	--report-interval=5 \
	--threads=256 \
	--time=$6 \
	run >> $7
