# GDBTuner

GDBTuner is a general auto tuner for database knobs. GDBTuner mainly use RL algorithm for auto tuning, which is cheaper and more efficient than DBA. 

## Preparation

### Install MySQL8 on Server

### Mysql Operations

create a new database:

```sql
create database gdbtuner;
```

show innoddb_metrics:

```sql
select name from INFORMATION_SCHEMA.innodb_metrics where status="enabled" order by name; 
```

create a new user and database:

```bash
# Login in as root
CREATE USER 'gdbtuner'@'localhost' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON * . * TO 'gdbtuner'@'localhost';
FLUSH PRIVILEGES;
CREATE database sbtest;
GRANT ALL PRIVILEGES ON sbtest TO 'gdbtuner'@'localhost';
FLUSH PRIVILEGES;
```

## Hyper Parameters

### Sysbench Related

workload type: read/write/read_write.

tables=8
table-size=100
report-interval=5 # report each 5 seconds.
threads=16 # for projgw, 128 is the highest.
time=20 # how long will we run sysbench.

## Ablation Study

### Reward Calculation

use best_performance or last_performance?

### Action Definition

Whether define action as the knobs' value, or define action as the increasing/decreasing length/bool of values.

### Minimal Score

use -10 or -50?

### Workload

number of tables and size of tables, and workload type.
