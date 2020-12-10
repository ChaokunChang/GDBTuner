import argparse
from math import log
import os
import gym
import ray
from ray import tune
from ray.rllib.agents import ddpg

from env.mysql import MySQLConnector, SysBenchSimulator, MySQLEnv


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop-iters", type=int, default=2)
    parser.add_argument("--stop-timesteps", type=int, default=10000)
    parser.add_argument("--stop-reward", type=float, default=150.0)
    parser.add_argument("--as-test", action="store_true")

    args = parser.parse_args()

    return args


if __name__ == "__main__":
    print("[INFO]: GDBT_HOME=", os.getenv("GDBT_HOME"))
    print("[INFO]: WORKLOAD_SRC=", os.getenv("WORKLOAD_SRC"))
    args = parse_args()

    ray.init()
    # connect to mysql
    mysql_config = {
        "host": "127.0.0.1",
        "port": "3306",
        "user": "gdbtuner",
        "password": "123456",
        "database": "sbtest",
        "memory": 8 * 1024
    }
    mysql_handle = MySQLConnector(mysql_config)

    # prepare sysbench
    sysbench_handle = SysBenchSimulator()

    config = {
        "env": MySQLEnv,  # "CarRacing-v0",
        "env_config": {
            "num_metrics": 74,
            "db_handle": mysql_handle,
            "simulator_handle": sysbench_handle,
        },
        "num_gpus": 0,
        "num_workers": 1,
        "framework": "torch",
        "learning_starts": 1500,
        "timesteps_per_iteration": 100,
        "evaluation_interval": 1,
        "evaluation_num_episodes": 1,
    }
    stop = {
        "training_iteration": args.stop_iters,
        "timesteps_total": args.stop_timesteps,
        "episode_reward_mean": args.stop_reward,
    }
    print("[INFO]: Start training.")
    results = tune.run(ddpg.DDPGTrainer, config=config, stop=stop, verbose=1)
    print("[INFO]: Finishe training.")

    if args.as_test:
        check_learning_achieved(results, args.stop_reward)
    ray.shutdown()
