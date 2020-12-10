import os
import time
import pexpect
import platform
import argparse
import ConfigParser as CP
import xmlrpc.server as RPCServer


class DBServer(object):
    docker = False

    def __init__(self, address, port):
        self.address = address
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
            prompt = r'\[sudo\] password for %s: ' % os.environ['USER']
        elif osname == 'Darwin':
            prompt = 'Password:'
        else:
            assert False, osname
        child = pexpect.spawn(cmdline)
        idx = child.expect([prompt, pexpect.EOF], 3)
        if idx == 0:
            child.sendline(passwd)
            child.expect(pexpect.EOF)
        return child.before


class MySQLServer(DBServer):
    def __init__(self, address="0.0.0.0", port=20000):
        DBServer.__init__(self, address, port)

    def serve(self):
        server = RPCServer((self.address, self.port))
        server.register_function(MySQLServer.start_db)
        server.register_function(MySQLServer.get_status)
        server.serve_forever()

    @staticmethod
    def start_db(db_name, db_conf):
        def write_cnf_file(configs):
            """Write the configs to my.cnf file.
            Args:
                configs: str, Formatted MySQL Parameters, e.g. "--binlog_size=xxx"
            """
            cnf_file = '/etc/mysql/my.cnf'

            # relax the permission of my.cnf
            DBServer.sudo_exec(f'sudo chmod 777 {cnf_file}', '123456')
            time.sleep(2)

            # use ConfigParser to handle cnf file
            config_parser = CP.ConfigParser()
            config_parser.read(cnf_file)
            for conf in configs:
                key, value = conf.split(':')
                config_parser.set('mysqld', key, value)

            # write back
            config_parser.write(open(cnf_file, 'w'))

            # restore the permission of my.cnf.
            DBServer.sudo_exec(f'sudo chmod 744 {cnf_file}', '123456')
            time.sleep(2)

        db_conf = db_conf.split(',')
        if DBServer.docker:
            # convert the configs to the format "--key=value", then pass them to docker container.
            docker_params = ''
            for conf in db_conf:
                key, value = conf.split(':')
                docker_params += f" --{key}={value}"

            # remove the current docker container.
            DBServer.sudo_exec(f"sudo docker stop {db_name}", '123456')
            DBServer.sudo_exec(f"sudo docker rm {db_name}", '123456')
            time.sleep(2)

            # start a new mysql container, which will launch a mysql instance.
            cmd = f"sudo docker run --name mysql1 -e MYSQL_ROOT_PASSWORD=12345678 -d -p 0.0.0.0:3365:3306 "
            cmd += f" -v /data/{db_name}/:/var/lib/mysql mysql:5.6 {docker_params}"
            print("[INFO]: Running: ", cmd)
            DBServer.sudo_exec(cmd, '123456')
        else:
            write_cnf_file(db_conf)

            # restart the database to activate the new configurations.
            DBServer.sudo_exec('sudo service mysql restart', '123456')

        time.sleep(5)
        return 1

    @staticmethod
    def get_status():
        """Service: get the current mysql status."""
        def check_start():
            a = DBServer.sudo_exec(
                'sudo tail -1 /var/log/mysql/ubunturmw.err', '123456')
            a = a.strip('\n\r')
            if a.find('pid ended') != -1:
                DBServer.sudo_exec('sudo service mysql start', '123456')

        check_start()
        output = os.popen('service mysql status')
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
