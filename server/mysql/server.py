import os
import time
import pexpect
import platform
import argparse
import configparser as CP
from xmlrpc.server import SimpleXMLRPCServer


class DBServer(object):
    docker = False

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.services = []  # list of functions.

    def serve(self):
        """Register services and start the server."""
        pass

    @staticmethod
    def start_db(db_conn, db_conf):
        """Service: start/restart db.
        Args:
            db_conn: str, the serialized attributes of DBConnector.
            db_conf: str, the serialized configurations for db.
        """
        pass

    @staticmethod
    def get_status():
        """Service: get the current db status."""
        pass

    @staticmethod
    def sudo_exec(cmdline, passwd):
        osname = platform.system()
        if osname == 'Linux':
            prompt = f"\[sudo\] password for {os.environ['USER']}:"
        elif osname == 'Darwin':
            prompt = 'Password:'
        else:
            assert False, osname
        child = pexpect.spawn(cmdline)
        idx = child.expect([prompt, pexpect.EOF], 30)
        if idx == 0:
            print("[INFO]: sudo_exec idx==0")
            child.sendline(passwd)
            child.expect(pexpect.EOF)
        else:
            print("[INFO]: sudo_exec idx!=0")
        return child.before


class MySQLServer(DBServer):
    def __init__(self, ip="0.0.0.0", port=20000):
        DBServer.__init__(self, ip, port)

    def serve(self):
        server = SimpleXMLRPCServer((self.ip, self.port))
        server.register_function(MySQLServer.start_db)
        server.register_function(MySQLServer.get_status)
        server.serve_forever()

    @staticmethod
    def start_db(db_name, db_conf):
        print("[INFO] Start db service. dname={}, dbconf={}".format(db_name, db_conf))

        def write_cnf_file(configs):
            """Write the configs to my.cnf file.
            Args:
                configs: str, Formatted MySQL Parameters, e.g. "--binlog_size=xxx"
            """
            cnf_file = '/etc/my.cnf.d/mysql-server.cnf'

            # relax the permission of my.cnf
            DBServer.sudo_exec(f'sudo chmod 777 {cnf_file}', 'ckchang_123')
            time.sleep(2)

            # use ConfigParser to handle cnf file
            config_parser = CP.ConfigParser()
            config_parser.read(cnf_file)
            # remove legacy knobs but preserving system knobs
            system_fields = ['datadir', 'socket', 'log-error', 'pid-file']
            for k in config_parser['mysqld']:
                if k not in system_fields:
                    config_parser.remove_option('mysqld', k)
            for conf in configs:
                key, value = conf.split(':')
                config_parser.set('mysqld', key, value)

            # write back
            config_parser.write(open(cnf_file, 'w'))
            print("[INFO] new conf written. ")

            # restore the permission of my.cnf.
            DBServer.sudo_exec(f'sudo chmod 744 {cnf_file}', 'ckchang_123')
            time.sleep(2)

        db_conf = db_conf.split(',')
        if DBServer.docker:
            # convert the configs to the format "--key=value", then pass them to docker container.
            docker_params = ''
            for conf in db_conf:
                key, value = conf.split(':')
                docker_params += f" --{key}={value}"

            # remove the current docker container.
            DBServer.sudo_exec(f"sudo docker stop {db_name}", 'ckchang_123')
            DBServer.sudo_exec(f"sudo docker rm {db_name}", 'ckchang_123')
            time.sleep(2)

            # start a new mysql container, which will launch a mysql instance.
            cmd = f"sudo docker run --name mysql1 -e MYSQL_ROOT_PASSWORD=12345678 -d -p 0.0.0.0:3365:3306 "
            cmd += f" -v /data/{db_name}/:/var/lib/mysql mysql:5.6 {docker_params}"
            print("[INFO]: Running: ", cmd)
            DBServer.sudo_exec(cmd, 'ckchang_123')
        else:
            write_cnf_file(db_conf)

            # restart the database to activate the new configurations.
            DBServer.sudo_exec('sudo systemctl restart mysqld', 'ckchang_123')
            print("[INFO]: Restart mysql finished.")

        time.sleep(5)
        return 1

    @staticmethod
    def get_status():
        """Service: get the current mysql status."""
        def check_start():
            a = DBServer.sudo_exec(
                'sudo tail -1 /var/log/mysql/ubunturmw.err', 'ckchang_123')
            a = a.strip('\n\r')
            if a.find('pid ended') != -1:
                DBServer.sudo_exec('sudo systemctl restart mysqld', 'ckchang_123')

        check_start()
        output = os.popen('systemctl status mysqld')
        status = output.readlines()[2]
        status = status.split(':')[1].replace(' ', '').split('(')[0]
        if status == 'failed':
            return -1
        return 1


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true')
    opt = parser.parse_args()
    if opt.docker:
        docker = True
    dbs = MySQLServer()
    dbs.serve()
