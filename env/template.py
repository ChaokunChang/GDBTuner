class DBEnv(object):

    def __init__(self, num_metrics, db_handle=None, simulator_handle=None):
        """Initialize the ENV
        Args:
            db_handle: DBHandle, object holding the db connection (incluing the db type).
            simulator_handle: SimHandle, object holding the simulator connection, usually a script.
        Returns: None
        """
        self.db_handle = db_handle
        self.simulator_handle = simulator_handle
        self.env_type = None

        self.steps = 0
        self.done = False
        self.num_metrics = num_metrics
        self.last_performance_metrics = None
        self.default_performance_metrics = None
        self.best_performance_metrics = None
        pass

    def reset(self):
        """ Reset the environment, which will be called in each episode.
        Args: None
        Returns: None
        """
        pass

    def step(self, action):
        """ Update the env according to the action chosen by agent.
        Args: 
            action: Knob, the action chosen by agent.
        Returns: 
            reward: float, the reward according to current db performance.
            next_state: Metrics, the state after taking the action.
            done: boolean, whether reaching the end of current episode.
            info: dict, the other information needed by trainer.
            ...
        """
        pass

    # def _get_reward(self, performance_metrics):
    #     """
    #     Args:
    #         performance_metrics: list, metrics that evaluates the performance of db, including `tps` and `qps`
    #     Return:
    #         reward: float, a scalar reward
    #     """
    #     pass

    # def _get_state(self, knobs):
    #     """Collect the metrics after applying the knobs, including the interal metrics that can be seen as state,
    #     and the external performance metrics that can be used to calculate rewards.
    #     Args:
    #         knobs: dict, the db settings.
    #     Returns:
    #         state_metrics: the metrics that can be seen as state of env
    #         performance_metrics: the metrics that can be used to calculate rewards.
    #     """
    #     state_metrics = self._get_db_metrics()
    #     if self.simulator_handle.type == 'sysbench':
    #         # calculate the sysbench time automaticly, but I don't know what does it mean ...
    #         if knobs['innodb_buffer_pool_size'] < 161061273600:
    #             time_sysbench = 150
    #         else:
    #             time_sysbench = int(
    #                 knobs['innodb_buffer_pool_size']/1024.0/1024.0/1024.0/1.1)
    #         self.simulator_handle.time = time_sysbench
    #     performance_metrics = self.simulator_handle.execute()
    #     return state_metrics, performance_metrics


class DBInstance(object):
    def __init__(self, config: dict):
        self.host = config['host']
        self.port = config['port']
        self.user = config['user']
        self.password = config['password']
        self.database = config['database']
        self.memory = config['memory']
        self.type = None


class SimulatorInstance(object):
    def __init__(self, workload="read"):
        self.workload = workload
        self.type = None

    def execute(self, config):
        # start a simulation process in python, and get the result.
        pass
