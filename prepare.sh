export GDBT_HOME=$PWD
export WORKLOAD_SRC="/usr/share/sysbench/"

# test sysbench
if [ ${1} == "read" ]
then
    run_script=${WORKLOAD_SRC}"oltp_read_only.lua"
elif [ ${1} == "write" ]
then
    run_script=${WORKLOAD_SRC}"oltp_write_only.lua"
else
    run_script=${WORKLOAD_SRC}"oltp_read_write.lua"
fi

sysbench ${run_script} \
	--mysql-host=$2 \
	--mysql-port=$3 \
	--mysql-user=gdbtuner \
	--mysql-password=$4 \
	--mysql-db=sbtest \
	--db-driver=mysql \
	--tables=200 \
	--table-size=10000000 \
	--report-interval=10 \
	--threads=16 \
	--time=5 \
	prepare
