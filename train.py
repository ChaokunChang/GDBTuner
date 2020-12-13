import argparse
from ast import parse
from math import log
import os
import gym
import ray
from ray import tune
from ray.rllib.agents import ddpg

from env.mysql import MySQLConnector, SysBenchSimulator, MySQLEnv


def parse_args():
    parser = argparse.ArgumentParser()

    # Ray related arguments
    parser.add_argument("--stop-timesteps", type=int, default=400)
    parser.add_argument("--knobs-set", type=str, default="mini_knobs")
    parser.add_argument("--as-test", action="store_true")
    parser.add_argument("--steps-per-iter", type=int, default=40)
    parser.add_argument("--checkpoint-freq", type=int, default=1)
    # parser.add_argument("--stop-iters", type=int, default=10)
    # parser.add_argument("--stop-reward", type=float, default=100)

    # Env related arguments
    parser.add_argument("--max-episode-length", type=int, default=50)
    parser.add_argument("--minimal_score", type=float, default=-10.0)
    parser.add_argument("--num_metrics", type=int, default=74)

    # Simulator related arguments
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
        "memory": 4 * 1024 * 1024 * 1024,  # Bytes = 4GB
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
        "train_batch_size": 16,
        "tau": 1e-5,
        "actor_lr": 1e-5,
        "critic_lr": 1e-5,
        "gamma": 0.9,
        "buffer_size": 100000,
        "learning_starts": 0,
        "timesteps_per_iteration": args.steps_per_iter,
        "evaluation_interval": 0,
        "evaluation_num_episodes": 0,
    }
    stop = {
        "timesteps_total": args.stop_timesteps,
        # "training_iteration": args.stop_iters,
        # "episode_reward_mean": args.stop_reward,
    }
    print("[INFO]: Start training.")
    results = tune.run(ddpg.DDPGTrainer, config=config, stop=stop,
                       checkpoint_freq=args.checkpoint_freq, verbose=1)
    print("[INFO]: Finished training.")

    if args.as_test:
        check_learning_achieved(results, args.stop_reward)
    ray.shutdown()
