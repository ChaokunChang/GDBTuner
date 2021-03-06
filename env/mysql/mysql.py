import time
import os
import re
import math
import threading
import math
import json
import pymysql
import http
from xmlrpc.client import ServerProxy, Transport, Fault

import numpy as np

from gym import spaces

from .knobs import MySQLKnobs
from .. import utils
from ..template import DBEnv, DBConnector, SimulatorConnector


class TimeoutTransport(Transport):
    timeout = 30.0

    def set_timeout(self, timeout):
        self.timeout = timeout

    def make_connection(self, host):
        h = http.client.HTTPConnection(host, timeout=self.timeout)
        return h


class MySQLConnector(DBConnector):
    def __init__(self, config: dict, instance_name="mysql1"):
        DBConnector.__init__(self, config)
        self.type = 'mysql'
        self.instance_name = instance_name

    def get_connection(self, retry_count=1, retry_interval=0):
        for i in range(retry_count):
            try:
                db_connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    passwd=self.password
                )
            except pymysql.Error as e:
                print(f"[FAIL]: Get connection failed in {i+1}th try.", e)
                time.sleep(retry_interval)
            else:
                print(f"[INFO]: Get connection succeed in {i+1}th try.")
                return db_connection
        return None

    def test_connection(self, retry_count=300, retry_interval=5):
        for i in range(retry_count):
            try:
                db_connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    passwd=self.password
                )
            except pymysql.Error as e:
                print(
                    f"[FAIL]: Test connection to db failed in {i+1}th try.", e)
                time.sleep(retry_interval)
            else:
                print(f"[INFO]: Test connection succeed in {i+1} times try.")
                db_connection.close()
                return True
        return False

    def get_metrics(self):
        db_connection = self.get_connection()
        if db_connection is None:
            return None
        cursor = db_connection.cursor()
        cmd = 'SELECT NAME, COUNT from information_schema.INNODB_METRICS where status="enabled" ORDER BY NAME'
        cursor.execute(cmd)
        data = cursor.fetchall()
        db_connection.close()
        return dict(data)

    def update_configuration(self, knobs):
        # First disconnect the db to avoid error as it will be restarted.
        # self.disconnect()

        # establish rpc proxy to db server.
        transport = TimeoutTransport()
        transport.set_timeout(60)
        sp = ServerProxy(
            f"http://0.0.0.0:20000", transport=transport)

        # prepare params for start_db.
        configs = []
        for name in knobs.names:
            configs.append(f"{name}:{knobs[name]}")
        configs = ','.join(configs)

        # restart mysql through proxy.
        retry_count = 0
        while retry_count < 5:  # try 4 more times if failed in the first call.
            try:
                print("[INFO]: restart db through rpc ...")
                sp.start_db(self.instance_name, configs)
            except Fault as e:
                time.sleep(5)
                retry_count += 1
                print("[WARN]: rpc call failed, retrying ...", e)
            else:
                break
        if retry_count >= 5:
            print("[ERROR]: rpc call to start_db failed.")
            # raise Exception("[ERROR]: rpc call to MySQLServer failed.")
        return True


class SysBenchSimulator(SimulatorConnector):
    def __init__(self, executor_path="/usr/bin/sysbench",
                 output_path=os.path.join(
                     os.getenv("GDBT_HOME"), "data/sysbench/result.log"),
                 workload="read", tables=100, table_size=1e5,
                 running_time=150, report_interval=5, threads=16):
        SimulatorConnector.__init__(self, workload, output_path)
        self.executor_path = executor_path
        self.type = 'sysbench'
        self.tables = tables
        self.table_size = table_size
        self.running_time = running_time
        self.report_interval = report_interval
        self.threads = threads

    def execute(self, config):
        sysbench_path = os.getenv('WORKLOAD_SRC')
        if self.workload == "read":
            lua_path = os.path.join(sysbench_path, "oltp_read_only.lua")
        elif self.workload == "write":
            lua_path = os.path.join(sysbench_path, "oltp_write_only.lua")
        else:
            lua_path = os.path.join(sysbench_path, "oltp_read_write.lua")

        db_conn = config["db"]  # a DBConnector
        cmd_bin = f"sysbench {lua_path}"
        cmd_params = f" --mysql-host={db_conn.host} --mysql-port={db_conn.port}"
        cmd_params += f" --mysql-user={db_conn.user} --mysql-password={db_conn.password}"
        cmd_params += f" --mysql-db={db_conn.database} --db-driver=mysql"
        cmd_params += f" --mysql-storage-engine=innodb --range-size=100 --events=0 --rand-type=uniform"
        cmd_params += f" --tables={self.tables} --table-size={self.table_size} --threads={self.threads}"
        cmd_params += f" --time={self.running_time} --report-interval={self.report_interval}"
        cmd_run = f"run >> {self.output_path}"
        cmd = cmd_bin + " " + cmd_params + " " + cmd_run
        print(f"[INFO]: executing cmd: {cmd}")

        simulation_duration = time.time()
        os.system(cmd)
        simulation_duration = time.time() - simulation_duration
        if simulation_duration < 10:
            # Too small time cost means that the simulation failed.
            print(
                f"[WARN] You shouldn't finish simulation in {simulation_duration} seconds.")
            return None
        return self.load_evaluations()

    def load_evaluations(self):
        with open(self.output_path) as f:
            lines = f.read()
        temporal_pattern = re.compile(
            "tps: (\d+.\d+) qps: (\d+.\d+) \(r/w/o: (\d+.\d+)/(\d+.\d+)/(\d+.\d+)\)"
            " lat \(ms,95%\): (\d+.\d+) err/s: (\d+.\d+) reconn/s: (\d+.\d+)")
        temporal = temporal_pattern.findall(lines)
        print(
            f"[INFO]: {len(temporal[-10:])} evaulation samples: ", temporal[-10:])
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
        print(f"[INFO]: performance: tps={tps}, latency={latency}, qps={qps}")
        return [tps, latency, qps]


class MySQLEnv(DBEnv):

    def __init__(self, config):
        DBEnv.__init__(self, config)
        self.env_type = 'mysql-v0'
        self.score = 0.0
        self.minimal_score = config.get('minimal_score', -10.0)

        self.knobs = MySQLKnobs(
            self.db_handle.knobs_set, self.db_handle.memory)

        self.action_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(self.knobs.num_knobs,),
            dtype=np.float32
        )
        # it's hard to know the low and high of state
        # thus we set it as unbounded
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.num_metrics,),
            dtype=np.float32
        )

    def reset(self):
        self.episode_length = 0
        self.score = 0
        self.last_performance_metrics = []
        self.best_performance_metrics = None
        self.done = False
        self.knobs = MySQLKnobs(
            self.db_handle.knobs_set, self.db_handle.memory)
        self.progress.append([])

        # apply the default knobs to db
        retry_count = 0
        applying_duration = time.time()
        while not self._apply_knobs(self.knobs) and retry_count < 5:
            retry_count += 1
            print(
                f"[WARN]: appling knobs failed, retrying the {retry_count} times ...")
        if retry_count == 5:
            print(
                f"[FATL]: appling knobs failed after {retry_count} times trying.")
        applying_duration = time.time() - applying_duration

        # get db states applying the knobs to db.
        state_metrics, performance_metrics = self._get_state(
            knobs=self.knobs)
        self.last_performance_metrics = performance_metrics
        self.default_performance_metrics = performance_metrics
        state = state_metrics
        # self.knobs.save(
        #     metrics=performance_metrics, knob_file=os.path.join(
        #         self.experiment_dir, "knob_metrics.txt"))

        step_log = {"step": -1}  # -1 means the reset
        step_log["knobs"] = self.knobs.as_dict()
        step_log["applying_duration"] = applying_duration
        step_log["next_state"] = state_metrics.tolist()
        step_log["tps"] = performance_metrics[0]
        step_log["lat"] = performance_metrics[1]
        step_log["qps"] = performance_metrics[2]
        step_log["cur_tps_lat"] = float(step_log["tps"]) / step_log["lat"]
        step_log["reward"] = 0
        step_log["score"] = 0
        step_log["best_tps_lat"] = step_log["cur_tps_lat"]
        self.progress[-1].append(step_log)

        return state

    def step(self, action):
        print(
            f"[INFO]: Running the {self.episode_length}th step of current episode.")
        step_log = {"step": self.episode_length}
        # apply action to update knobs
        self.knobs.apply_action(action)
        step_log["knobs"] = self.knobs.as_dict()

        # record the time cost of applying the new knobs to db
        applying_duration = time.time()
        succeed = self._apply_knobs(self.knobs)
        applying_duration = time.time() - applying_duration
        step_log["applying_duration"] = applying_duration

        # if we failed to apply the new knob, return inf-empty
        failed_info = {"score": self.score - 1e7, "performance_metrics": [0, 0, 0],
                       "applying_duration": applying_duration}
        failed_ret = np.array([0] * self.num_metrics), -1e7, True, failed_info
        if not succeed:
            print("[WARN]: apply_knobs not succedd, return failed_ret")
            self.done = True
            return failed_ret
        state_metrics, performance_metrics = self._get_state(self.knobs)
        if performance_metrics is None or state_metrics is None:
            print("[WARN]: _get_state return None, return failed_ret")
            self.done = True
            return failed_ret

        step_log["next_state"] = state_metrics.tolist()
        step_log["tps"] = performance_metrics[0]
        step_log["lat"] = performance_metrics[1]
        step_log["qps"] = performance_metrics[2]
        step_log["cur_tps_lat"] = float(step_log["tps"]) / step_log["lat"]
        # save the knobs and metrics
        # self.knobs.save(
        #     metrics=performance_metrics, knob_file=os.path.join(
        #         self.experiment_dir, "knob_metrics.txt"))

        # get rewards, nxt_state, done, and info for current step.
        reward = self._get_reward(performance_metrics)
        step_log["reward"] = reward
        step_log["score"] = self.score

        next_state = state_metrics
        info = {"score": self.score, "performance_metrics": performance_metrics,
                "applying_duration": applying_duration}

        # update the best performance records, which will be used by reward calculation
        if self._update_best_performance(performance_metrics):
            print("[INFO]: Best performance updated!")
            self.last_performance_metrics = self.best_performance_metrics
        else:
            print("[INFO]: Best performance remained.")
        step_log["best_tps_lat"] = float(self.last_performance_metrics[0]) / \
            self.last_performance_metrics[1]

        self.progress[-1].append(step_log)
        # stop episode if accumulated reward is too low
        # if the accumulated reward is less than -10, we consider end.
        if self.score < self.minimal_score:
            print(
                f"[INFO]: End of episode reached with {self.episode_length} steps, because score = {self.score} < -10.0 .")
            self.done = True
        if self.episode_length >= self.max_episode_length:
            print(
                f"[INFO]: End of episode reached with {self.episode_length} steps, because max episode length.")
            self.done = True

        if self.done:
            progress_i_file_path = os.path.join(
                self.experiment_dir, f"progress_{len(self.progress)}.json")
            with open(progress_i_file_path, 'w') as f:
                f.write(json.dumps(self.progress[-1]))
            progress_file_path = os.path.join(
                self.experiment_dir, "progress.json")
            with open(progress_file_path, 'w') as f:
                f.write(json.dumps(self.progress))

        return next_state, reward, self.done, info

    def _get_db_metrics(self, db_metrics_holder):
        """Collect db metrics using multiple threads, then aggregate the results.
        Args:
            db_metrics_holder: list of dict, a list that hold all the metrics collected from db while sysbench testing.
        Returns:
            db_metrics_holder: list of dict, same as input.
        """

        # how long the collecting thread will survive.
        collecting_time = self.simulator_handle.report_interval  # default 5
        # how many threads will be launched to collect metrics.
        collector_num = self.simulator_handle.running_time / \
            collecting_time + 1  # default 75/5 + 1= 16

        def collect_metric(collector_id):
            collector_id += 1
            timer = threading.Timer(
                collecting_time, collect_metric, (collector_id,))
            timer.start()
            if collector_id >= collector_num:
                timer.cancel()
            try:
                data = self.db_handle.get_metrics()
                if data is None:
                    print(
                        f"[INFO]: Collector{collector_id}/{collector_num} failed by no connection.")
                else:
                    db_metrics_holder.append(data)
            except Exception as err:
                print(
                    f"[INFO]: Collector{collector_id}/{collector_num} failed by exception {err}")
            else:
                print(
                    f"[INFO]: Collector{collector_id}/{collector_num} finished collecting.")

        collect_metric(0)  # launch the threads to collect metrics.

        return db_metrics_holder

    def _aggregate_db_metrics(self, db_metrics):
        """Collect
        Args:
            db_metrics, list of dict, the metrics collected from collector threads.
        Returns:
            state_metrics, np.array(float), the aggregated metrics as state metrics.
        """
        state_metrics = np.zeros(self.num_metrics)

        def do(metric_name, metric_values):
            metric_type = utils.get_metric_type(metric_name)
            if metric_type == 'counter':
                return float(metric_values[-1] - metric_values[0])
            else:
                return float(sum(metric_values))/len(metric_values)

        # print(f"[DEBUG]: {len(db_metrics)}metrics", db_metrics)
        keys = list(db_metrics[0].keys())
        keys.sort()

        for idx in range(len(keys)):
            key = keys[idx]
            data = [x[key] for x in db_metrics]
            state_metrics[idx] = do(key, data)

        print(
            f"[DEBUG]: aggreated {len(db_metrics)} metrics and get state_metrics", state_metrics)
        return state_metrics

    def _get_state(self, knobs):
        """Collect the metrics after applying the knobs, including the interal metrics that can be seen as state,
        and the external performance metrics that can be used to calculate rewards.
        Args:
            knobs: MySQLKnobs, the db settings.
        Returns:
            state_metrics: np.ndarray(float), the metrics that can be seen as state of env
            performance_metrics: list of float, the metrics that can be used to calculate rewards.
        """
        # get state metrics from db
        db_metrics = []

        # prepare configs for workload simulator.
        simulator_config = {"db": self.db_handle}  # configs for simulator
        if self.simulator_handle.type == 'sysbench':
            # calculate the sysbench time automaticly, but I don't know what does it mean ...
            if knobs['innodb_buffer_pool_size'] < 75 * 1024 * 1024 * 1024:  # 75GB
                time_sysbench = 75
            else:
                time_sysbench = int(
                    knobs['innodb_buffer_pool_size']/1024.0/1024.0/1024.0/1.1)
            self.simulator_handle.running_time = time_sysbench

        # collect db metrics through rpc server, asynchronously collecting. expect to finish with simulator testing.
        self._get_db_metrics(db_metrics)
        # get performance metrics through workload simulator.
        performance_metrics = self.simulator_handle.execute(simulator_config)
        state_metrics = self._aggregate_db_metrics(db_metrics)
        return state_metrics, performance_metrics

    def _get_reward(self, performance_metrics):
        """
        Args:
            performance_metrics: list, metrics that evaluates the performance of db, including `tps` and `qps`
        Return:
            reward: float, a scalar reward
        """
        print(
            f"[INFO]: (current,default,last) performance metrics: ({performance_metrics}, {self.default_performance_metrics}, {self.last_performance_metrics})")

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
            (performance_metrics[0] - self.default_performance_metrics[0]))/self.default_performance_metrics[0]
        delta_t_tps = float(
            (performance_metrics[0] - self.last_performance_metrics[0]))/self.last_performance_metrics[0]

        tps_reward = reward_calculation(delta_0_tps, delta_t_tps)

        # latency
        delta_0_lat = float(
            (-performance_metrics[1] + self.default_performance_metrics[1])) / self.default_performance_metrics[1]
        delta_t_lat = float(
            (-performance_metrics[1] + self.last_performance_metrics[1])) / self.last_performance_metrics[1]

        lat_reward = reward_calculation(delta_0_lat, delta_t_lat)

        reward = tps_reward * 0.4 + 0.6 * lat_reward
        self.score += reward

        print(
            f"[INFO]: Reward: {reward} =  0.4 * {tps_reward} + 0.6 * {lat_reward}")
        print(f"[INFO]: Score = {self.score}")

        if reward > 0:
            reward = reward * 1e6

        return reward

    def _update_best_performance(self, metrics):
        """Update best performance and record it if changed.
        Args:
            metrics: list, the new metrics generate in current episode.
        Returns:
            updated: boolean, whether the best performance has changed.
        """
        updated = False
        cur_tps = metrics[0]
        cur_lat = metrics[1]
        if int(cur_lat) != 0:
            cur_rate = float(cur_tps) / cur_lat
            if self.best_performance_metrics is None:
                best_rate = -math.inf
            else:
                best_rate = float(
                    self.best_performance_metrics[0]) / self.best_performance_metrics[1]
            if cur_rate > best_rate:
                updated = True
                self.best_performance_metrics = metrics
                # with open(f"{os.getenv('GDBT_HOME', '.')}/bestnow.log", "w") as f:
                #     f.write(str(cur_tps) + ',' +
                #             str(cur_lat) + ',' + str(cur_rate))
        return updated

    def _apply_knobs(self, knobs):
        """ Apply the knobs to the db instance
        Args:
            knobs: MySQLKnobs, mysql parameters.
        Returns:
            succeed: boolean, whether the applying succeed.
        """
        # apply the knobd to db, which will cause db to restart.
        self.db_handle.update_configuration(knobs)
        self.episode_length += 1

        if self.db_handle.test_connection(retry_count=300, retry_interval=5):
            # if we can connect to the db after applying new knobs,
            # it means that the db has already been restarted.
            return True
        else:
            # if we can not connect to the db anymore.
            print(print("[FAIL]: The database is not running, check it."))
            self.knobs = MySQLKnobs(
                self.db_handle.knobs_set, self.db_handle.memory)
            self.db_handle.update_configuration(self.knobs)
            print("[FAIL]: Failed to apply the new knobs to db.")
            log_str = ""
            for key in knobs.names:
                log_str += f" --{key}={knobs[key]}"
            with open(os.path.join(self.experiment_dir, "failed.log"), 'a+') as f:
                f.write(log_str+'\n')
                return False
