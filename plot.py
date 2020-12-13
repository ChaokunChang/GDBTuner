import os
import csv
import pickle
import argparse

import numpy as np
import matplotlib.pyplot as plt

from pprint import pprint
from env.mysql import MySQLKnobs


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--test-log-path", required=True)
    parser.add_argument("--save-path", default='figures')
    parser.add_argument("--show-figure", action="store_true")

    args = parser.parse_args()

    return args


def plot_reward(args):
    # plot reward mean/min/max
    train_log_path = os.path.join(args.checkpoint_path, 'progress.csv')
    with open(train_log_path, "r") as f:
        reader = csv.DictReader(f)
        timesteps = []
        reward_mean = []
        reward_min = []
        reward_max = []
        for row in reader:
            timesteps.append(int(row["timesteps_total"]))
            reward_min.append(float(row["episode_reward_min"]))
            reward_max.append(float(row["episode_reward_max"]))
            reward_mean.append(float(row["episode_reward_mean"]))

    fig = plt.figure()
    ax = plt.axes()
    ax.set_xlabel('Timestep')
    ax.set_ylabel('Reward')
    ax.set_xlim([min(timesteps) - 40, max(timesteps) + 40])
    ax.set_ylim([min(reward_min) * 4/5, max(reward_max) * 6/5])
    ax.plot(timesteps, reward_mean, '-', label='Reward Mean')
    ax.fill_between(timesteps, reward_min, reward_max, alpha=0.2, label='Reward Min/Max')
    ax.legend()

    if not os.path.exists(args.save_path):
        os.mkdir(args.save_path)

    # must put before plt.show(), otherwise it's cleaned
    plt.savefig(os.path.join(args.save_path, 'reward.pdf'))
    if args.show_figure:
        plt.show()


def find_best_knob(args):
    # find best knob in test
    with open(args.test_log_path, "rb") as f:
        result = pickle.load(f)

    best_index = -1
    best_delta = [0, 0, 0]
    default_tps, default_latency, default_qps = \
        result["default_metrics"]

    best_metrics = [default_tps, default_latency, default_qps]
    for i in range(result["steps"]):
        tps, latency, qps = result["info"][i]["performance_metrics"]
        tps_delta = (tps - default_tps) / default_tps * 100
        latency_delta = - (latency - default_latency) / default_latency * 100
        qps_delta = (qps - default_qps) / default_qps * 100

        delta = [tps_delta, latency_delta, qps_delta]
        if sum(delta) > sum(best_delta):
            best_index = i
            best_delta = delta
            best_metrics = [tps, latency, qps]

    print(f"[INFO]: Best Index: {best_index} / {result['steps']}")
    print("[INFO]: Default TPS: {}, Latency: {}, QPS: {}".format(*result["default_metrics"]))
    print("[INFO]: Best TPS: {}, Latency: {}, QPS: {}".format(*best_metrics))
    print("[INFO]: Best TPS%: {}, Latency%: {}, QPS%: {}".format(*best_delta))

    # apply action to get best knobs
    if best_index == -1:
        print("[WARNING]: No knobs better than default found!")
    else:
        action = result["action"][best_index]
        # TODO: isolate mysql config
        max_memory_size = 4 * 1024 * 1024 * 1024
        mysql_knobs = MySQLKnobs('mini_knobs', max_memory_size)
        mysql_knobs.apply_action(action)
        pprint(mysql_knobs.knobs)


if __name__ == "__main__":
    args = parse_args()

    plot_reward(args)

    find_best_knob(args)
