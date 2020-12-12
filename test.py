import argparse
from math import log
import os
import gym
import ray
import pickle
from ray import tune
from ray.rllib.agents import ddpg

from env.mysql import MySQLConnector, SysBenchSimulator, MySQLEnv


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--save-path", required=True)

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
        "memory": 4 * 1024 * 1024 * 1024, # Bytes = 4GB
        "knobs_set": "mini_knobs",
    }
    mysql_handle = MySQLConnector(mysql_config)

    # prepare sysbench
    sysbench_handle = SysBenchSimulator()

    config = {
        "num_metrics": 74,
        "db_handle": mysql_handle,
        "simulator_handle": sysbench_handle,
    }
    env = MySQLEnv(config)
    agent = ddpg.DDPGTrainer(config=config, env=MySQLEnv)
    agent.restore(args.checkpoint_path)

    done = False

    obs = env.reset()

    print("[INFO]: Start testing.")

    result = {
        "steps": 0,
        "default_metrics": env.default_performance_metrics,
        "action": [],
        "obs": [],
        "reward": [],
        "done": [],
        "info": [],
    }

    while not done:
        action = agent.compute_action(obs)
        obs, reward, done, info = env.step(action)

        result["action"].append(action)
        result["obs"].append(obs)
        result["reward"].append(reward)
        result["done"].append(done)
        result["info"].append(info)
        result["steps"] += 1

    episode_mean_reward = sum(result["reward"]) / result["steps"]

    with open(args.save_path, "wb") as f:
        pickle.dump(result, f)

    print(f"[INFO]: Result saved to {args.save_path}.")

    print(f"[INFO]: Mean Reward = {episode_mean_reward}")

    print("[INFO]: Finished testing.")
