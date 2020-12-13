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

    parser.add_argument("--knobs-set", type=str, default="mini_knobs")
    parser.add_argument("--max-episode-length", type=int, default=50)
    parser.add_argument("--minimal-score", type=float, default=-10.0)
    parser.add_argument("--num_metrics", type=int, default=74)
    parser.add_argument("--workload-type", type=str, default="read")

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
        "knobs_set": args.knobs_set,
    }
    mysql_handle = MySQLConnector(mysql_config)

    # prepare sysbench
    sysbench_handle = SysBenchSimulator(workload=args.workload_type)

    config = {
        "env": MySQLEnv,  # "CarRacing-v0",
        "env_config": {
            "num_metrics": args.num_metrics,
            "max_episode_length": args.max_episode_length,
            "minimal_score": args.minimal_score,
            "db_handle": mysql_handle,
            "simulator_handle": sysbench_handle,
        },
        "num_gpus": 0,
        "num_workers": 0,
        "framework": "torch",
        # "train_batch_size": 16,
        # "tau": 1e-5,
        # "actor_lr": 1e-5,
        # "critic_lr": 1e-5,
        # "gamma": 0.9,
        # "buffer_size": 100000,
        # "learning_starts": 0,
        # "timesteps_per_iteration": args.steps_per_iter,
        # "evaluation_interval": 0,
        # "evaluation_num_episodes": 0,
    }

    env = MySQLEnv(config["env_config"])
    agent = ddpg.DDPGTrainer(config=config)
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
