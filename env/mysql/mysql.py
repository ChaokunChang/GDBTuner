
import time
import os
import re
import math
import threading
import math
import json
import MySQLdb
import xmlrpc
import http

import numpy as np

from .. import utils
from ..template import DBEnv, DBInstance, SimulatorInstance


class TimeoutTransport(xmlrpc.client.Transport):
    timeout = 30.0

    def set_timeout(self, timeout):
        self.timeout = timeout

    def make_connection(self, host):
        h = http.client.HTTPConnection(host, timeout=self.timeout)
        return h


class MySQLInstance(DBInstance):
    def __init__(self, config: dict, instance_name="mysql1"):
        DBInstance.__init__(self, config)
        self.type = 'mysql'
        self.instance_name = instance_name

    def connect(self, retry_count=300, retry_interval=5):
        self.disconnect()
        for i in range(retry_count):
            try:
                self.db_connection = MySQLdb.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    passwd=self.password
                )
            except MySQLdb.Error as e:
                print("[FAIL]: ", e)
                time.sleep(retry_interval)
            else:
                return True
        return False

    def disconnect(self):
        if self.connected():
            self.db_connection.close()
        else:
            print("[WARN]: No connection now, disconnect invalid.")

    def get_metrics(self):
        if not self.connected():
            self.connect()
        cursor = self.db_connection.cursor()
        cmd = 'SELECT NAME, COUNT from information_schema.INNODB_METRICS where status="enabled" ORDER BY NAME'
        cursor.execute(cmd)
        data = cursor.fetchall()
        return dict(data)

    def update_configuration(self, config):
        """ Modify the configurations by restarting the mysql through Docker
        Args:
            config: dict, configurations
        """
        # First disconnect the db to avoid error as it will be restarted.
        self.disconnect()

        # establish rpc proxy to db server.
        transport = TimeoutTransport()
        transport.set_timeout(60)
        sp = xmlrpc.client.ServerProxy(
            f"http://{self.host}:20000", transport=transport)

        # prepare params for start_mysql.
        params = []
        for k, v in config.items():
            params.append(f"{k}:{v}")
        params = ','.join(params)

        # restart mysql through proxy.
        retry_count = 0
        while retry_count < 3:  # try 2 more times if failed in the first call.
            try:
                sp.start_mysql(self.instance_name, params)
            except xmlrpc.client.Fault:
                time.sleep(5)
                retry_count += 1
            else:
                break

        return True


class SysBenchSimulator(SimulatorInstance):
    def __init__(self, executor_path, output_path, workload="read"):
        SimulatorInstance.__init__(self, workload, output_path)
        self.executor_path = executor_path
        self.type = 'sysbench'

    def execute(self, config):
        metrics = None
        cmd_bin = f"bash {os.getenv('GDBT_HOME')}/scripts/run_sysbench.sh "
        cmd_params = f"{config['workload']} {config['host']} {config['port']} {config['passwd']} {config['time']} {self.output_path}"
        cmd = cmd_bin + " " + cmd_params
        print(f"[INFO]: executing cmd: {cmd}")
        simulation_duration = time.time()
        os.system(cmd)
        simulation_duration = time.time() - simulation_duration
        if simulation_duration < 50:
            # Too small time cost means that the simulation failed.
            return None
        time.sleep(10)  # [TODO] don't know why we need to wait ...
        return self.load_evaluations()

    def load_evaluations(self):
        with open(self.output_path) as f:
            lines = f.read()
        temporal_pattern = re.compile(
            "tps: (\d+.\d+) qps: (\d+.\d+) \(r/w/o: (\d+.\d+)/(\d+.\d+)/(\d+.\d+)\)"
            " lat \(ms,95%\): (\d+.\d+) err/s: (\d+.\d+) reconn/s: (\d+.\d+)")
        temporal = temporal_pattern.findall(lines)
        tps = 0
        latency = 0
        qps = 0

        for i in temporal[-10:]:
            tps += float(i[0])
            latency += float(i[5])
            qps += float(i[1])
        num_samples = len(temporal[-10:])
        tps /= num_samples
        qps /= num_samples
        latency /= num_samples
        return [tps, latency, qps]


class MySQLEnv(DBEnv):

    def __init__(self, num_metrics=63, db_handle=None, simulator_handle=None, knobs_helper=None):
        DBEnv.__init__(self, num_metrics, db_handle, simulator_handle)
        self.env_type = 'mysql-v0'
        self.score = 0.0
        self.knobs_helper = knobs_helper
        self.default_knobs = self.knob.get_init_knobs()

    def reset(self):
        self.steps = 0
        self.score = 0
        self.last_performance_metrics = []
        self.done = False

        # apply the default knobs to db
        retry_count = 0
        while not self._apply_knobs(self.default_knobs) and retry_count < 5:
            retry_count += 1
            print(
                f"[WARN]: appling knobs failed, retrying the {retry_count} times ...")
        if retry_count == 5:
            print(
                f"[FATL]: appling knobs failed after {retry_count} times trying.")

        # get db states applying the knobs to db.
        state_metrics, performance_metrics = self._get_state(
            knobs=self.default_knobs)
        self.last_performance_metrics = performance_metrics
        self.default_performance_metrics = performance_metrics
        state = state_metrics
        self.knobs_helper.save(
            knobs=self.default_knobs, metrics=performance_metrics, knob_file=f"{os.getenv('GDBT_HOME', '.')}/knob_metrics.txt")

        return state, performance_metrics

    def step(self, action):
        knobs = action

        # record the time cost of applying the new knobs to db
        applying_duration = time.time()
        succeed = self._apply_knobs(knobs)
        applying_duration = time.time() - applying_duration

        # if we failed to apply the new knob, return inf-empty
        failed_info = {"score": self.score - 10000000, "performance_metrics": [0, 0, 0],
                       "applying_duration": applying_duration}
        failed_ret = - \
            10000000.0, np.array([0] * self.num_metric), True, failed_info
        if not succeed:
            return failed_ret
        state_metrics, performance_metrics = self._get_state(knobs)
        if performance_metrics is None or state_metrics is None:
            return failed_ret

        # save the knobs and metrics
        self.knobs_helper.save(
            knobs=knobs, metrics=performance_metrics, knob_file=f"{os.getenv('GDBT_HOME', '.')}/knob_metrics.txt")

        # get rewards, nxt_state, done, and info for current step.
        reward = self._get_reward(performance_metrics)
        next_state = state_metrics
        done = self.done
        info = {"score": self.score, "performance_metrics": performance_metrics,
                "applying_duration": applying_duration}

        # update the best performance records, which will be used by reward calculation
        if self._update_best_performance(performance_metrics):
            print("[INFO]: Best performance updated!")
            self.last_performance_metrics = self.best_performance_metrics
        else:
            print("[INFO]: Best performance remained.")

        return reward, next_state, done, info

    def _get_db_metrics(self):
        """Collect db metrics using multiple threads, then aggregate the results.
        Returns: 
            db_metrics: list, the aggregated metrics
        """
        metrics = []
        _counter = 0
        _period = 5
        count = 160/5

        def collect_metric(counter):
            counter += 1
            timer = threading.Timer(_period, collect_metric, (counter,))
            timer.start()
            if counter >= count:
                timer.cancel()
            try:
                data = self.db_handle.get_metrics()
                metrics.append(data)
            except Exception as err:
                print("[GET Metrics]Exception:", err)

        collect_metric(_counter)
        # time.sleep(5)

        # aggregate the metrics collected through multiple threads.
        db_metrics = np.zeros(self.num_metric)

        def do(metric_name, metric_values):
            metric_type = utils.get_metric_type(metric_name)
            if metric_type == 'counter':
                return float(metric_values[-1] - metric_values[0])
            else:
                return float(sum(metric_values))/len(metric_values)

        keys = metrics[0].keys()
        keys.sort()

        for idx in range(len(keys)):
            key = keys[idx]
            data = [x[key] for x in metrics]
            db_metrics[idx] = do(key, data)

        return db_metrics

    def _get_state(self, knobs):
        """Collect the metrics after applying the knobs, including the interal metrics that can be seen as state,
        and the external performance metrics that can be used to calculate rewards.
        Args: 
            knobs: dict, the db settings.
        Returns:
            state_metrics: the metrics that can be seen as state of env
            performance_metrics: the metrics that can be used to calculate rewards.
        """
        # get state metrics from db
        state_metrics = self._get_db_metrics()

        # get performance metrics through workload simulator.
        config = {}  # configs for simulator
        if self.simulator_handle.type == 'sysbench':
            # calculate the sysbench time automaticly, but I don't know what does it mean ...
            if knobs['innodb_buffer_pool_size'] < 161061273600:
                time_sysbench = 150
            else:
                time_sysbench = int(
                    knobs['innodb_buffer_pool_size']/1024.0/1024.0/1024.0/1.1)
            config['time'] = time_sysbench
        performance_metrics = self.simulator_handle.execute(config)
        return state_metrics, performance_metrics

    def _get_reward(self, performance_metrics):
        """
        Args:
            performance_metrics: list, metrics that evaluates the performance of db, including `tps` and `qps`
        Return:
            reward: float, a scalar reward
        """
        print('*****************************')
        print(f"[INFO]: (current,default,last) performance metrics: \n \
                ({performance_metrics}, {self.default_externam_metrics}, \
                    {self.last_performance_metrics})")
        print('*****************************')

        def reward_calculation(delta0, deltat):

            if delta0 > 0:
                _reward = ((1+delta0)**2-1) * math.fabs(1+deltat)
            else:
                _reward = - ((1-delta0)**2-1) * math.fabs(1-deltat)

            if _reward > 0 and deltat < 0:
                _reward = 0
            return _reward
        # tps
        delta_0_tps = float(
            (performance_metrics[0] - self.default_externam_metrics[0]))/self.default_externam_metrics[0]
        delta_t_tps = float(
            (~[0] - self.last_performance_metrics[0]))/self.last_performance_metrics[0]

        tps_reward = reward_calculation(delta_0_tps, delta_t_tps)

        # latency
        delta_0_lat = float(
            (-performance_metrics[1] + self.default_externam_metrics[1])) / self.default_externam_metrics[1]
        delta_t_lat = float(
            (-performance_metrics[1] + self.last_performance_metrics[1])) / self.last_performance_metrics[1]

        lat_reward = reward_calculation(delta_0_lat, delta_t_lat)

        reward = tps_reward * 0.4 + 0.6 * lat_reward
        self.score += reward

        print('$$$$$$$$$$$$$$$$$$$$$$')
        print(f"[INFO]: Reward: {reward} =  \
            0.4 * {tps_reward} + 0.6 * {lat_reward}")
        print('$$$$$$$$$$$$$$$$$$$$$$')

        if reward > 0:
            reward = reward*1000000

        return reward

    def _update_best_performance(self, metrics):
        """Update best performance and record it if changed.
        Args:
            metrics: list, the new metrics generate in current episode.
        Returns:
            updated: boolean, whether the best performance has changed.
        """
        updated = False
        best_tps = self.best_performance_metrics[0]
        best_lat = self.best_performance_metrics[0]
        cur_tps = metrics[0]
        cur_lat = metrics[1]
        if int(cur_lat) != 0:
            cur_rate = float(cur_tps) / cur_lat
            best_rate = float(best_tps) / best_lat
            if cur_rate > best_rate:
                updated = True
                self.best_performance_metrics = metrics
                with open(f"{os.getenv('GDBT_HOME', '.')}/bestnow.log", "w") as f:
                    f.write(str(cur_tps) + ',' +
                            str(cur_lat) + ',' + str(cur_rate))
        return updated

    def _apply_knobs(self, knobs):
        """ Apply the knobs to the db instance
        Args:
            knobs: dict, mysql parameters.
        Returns:
            succeed: boolean, whether the applying succeed.
        """
        # apply the knobd to db, which will cause db to restart.
        self.db_handle.update_configuration(knobs)
        self.steps += 1

        if self.db_handle.connect(retry_count=300, retry_interval=5):
            # if we can connect to the db after applying new knobs,
            return True
        else:
            # if we can not connect to the db anymore.
            self.db_handle.update_configuration(self.default_knobs)
            print("[FAIL]: Failed to apply the new knobs to db.")
            log_str = ""
            for key in knobs.keys():
                log_str += f" --{key}={knobs[key]}"
            with open(f"{os.getenv('GDBT_HOME', '.')}/failed.log", 'a+') as f:
                f.write(log_str+'\n')
                return False
