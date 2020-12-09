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


class DBInstance(object):
    def __init__(self, config: dict):
        self.host = config['host']
        self.port = config['port']
        self.user = config['user']
        self.password = config['password']
        self.database = config['database']
        self.memory = config['memory']
        self.type = None
        self.db_connection = None

    def connect(self, retry_count, retry_interval):
        pass

    def connected(self):
        return self.db_connection is not None

    def disconnect(self):
        pass

    def get_metrics(self):
        pass

    def update_configuration(self, config):
        pass


class SimulatorInstance(object):
    def __init__(self, workload="read", output_path=None):
        self.workload = workload
        self.type = None
        self.output_path = output_path

    def execute(self, config):
        """Start a simulation process in python, and get the result.
        Args:
            config: dict, the configs needed by runing simulator.
        Returns: 
            metrics: list of float, the performace under current simulating workload. 
        """
        pass

    def load_evaluations(self):
        """Load and parse the last evaluation results from self.output_path
        Returns:
            metrics: list, the evaluation results.
        """
        pass
