import gym
import time
import datetime
import os


class DBEnv(gym.Env):

    def __init__(self, config: dict):
        """Initialize the ENV
        Args:
            config: Configuration for environment
        Returns: None
        """
        self.db_handle = config["db_handle"]
        self.simulator_handle = config["simulator_handle"]
        self.env_type = None

        self.knobs = None
        self.episode_length = 0
        self.max_episode_length = config.get("max_episode_length", 50)
        self.done = False
        self.num_metrics = config.get("num_metrics", 74)
        self.last_performance_metrics = None
        self.default_performance_metrics = None
        self.best_performance_metrics = None
        self.experiment_id = datetime.datetime.fromtimestamp(
            int(time.time())).strftime("%Y-%m-%d-%H%M%S")
        self.gdbt_home = os.getenv("GDBT_HOME")
        self.experiment_path = os.path.join(
            self.gdbt_home, f"data/experiments/{self.experiment_id}")
        if not os.path.exists(self.experiment_path):
            os.mkdir(self.experiment_path)
        if self.simulator_handle is not None:
            self.simulator_handle.output_path = os.path.join(self.experiment_path,"sysbench_result.log")

    def reset(self):
        """ Reset the environment, which will be called in each episode.
        Args: None
        Returns:
            observation: Metrics, the state after taking the action.
        """
        pass

    def step(self, action):
        """ Update the env according to the action chosen by agent.
        Args:
            action: Knob, the action chosen by agent.
        Returns:
            observation: Metrics, the state after taking the action.
            reward: float, the reward according to current db performance.
            done: boolean, whether reaching the end of current episode.
            info: dict, the other information needed by trainer.
        """
        pass


class DBConnector(object):
    def __init__(self, config: dict):
        self.host = config['host']
        self.port = int(config['port'])
        self.user = config['user']
        self.password = config['password']
        self.database = config['database']
        self.memory = config['memory']
        self.knobs_set = config['knobs_set']
        self.type = None

    def connect(self, retry_count, retry_interval):
        pass

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
            value = self.min_value + \
                int((self.max_value - self.min_value) * action)
        elif self.knob_type == 'float':
            value = self.min_value + ((self.max_value - self.min_value) * action)
        elif self.knob_type == 'bool':
            value = int(x > 0.5)
        else:
            raise NotImplementedError

        self.value = value
