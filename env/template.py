class DBEnv(object):

    def __init__(self, num_metrics, db_handle=None, simulator_handle=None):
        """Initialize the ENV
        Args:
            db_handle: DBConnector, object holding the db connection (incluing the db type).
            simulator_handle: SimulatorConnector, object holding the simulator connection.
        Returns: None
        """
        self.db_handle = db_handle
        self.simulator_handle = simulator_handle
        self.env_type = None

        self.knobs = None
        self.steps = 0
        self.done = False
        self.num_metrics = num_metrics
        self.last_performance_metrics = None
        self.default_performance_metrics = None
        self.best_performance_metrics = None

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


class DBConnector(object):
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
        """ Get the state of db
        Returns:
            data: dict, status of db in dict format, which can be seen as metrics.
        """
        pass

    def update_configuration(self, config):
        """ Modify the configurations by restarting the db through Docker
        Args:
            config: dict, configurations
        """
        pass


class SimulatorConnector(object):
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
            metrics: list of float, the performace under current simulating workload.
        """
        pass


class Knob(object):
    def __init__(self, config: dict):
        self.name = config["name"]
        self.value = config["default"]
        self.min_value, self.max_value = config["range"]
        self.knob_type = config["type"]

    def __repr__(self):
        return f"{self.value}"

    def apply_action(self, action):
        if self.knob_type == 'int':
            value = self.min_value + int((self.max_value - self.min_value) * action)
        else:
            raise NotImplementedError

        self.value = value
