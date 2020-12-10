# GDBTuner

GDBTuner is a general auto tuner for database knobs. GDBTuner mainly use RL algorithm for auto tuning, which is cheaper and more efficient than DBA. 

## Preparation

### Install Mysql on server

### Mysql operations

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
