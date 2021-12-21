#!python3
"""
Author: Hansheng Chen
Email:  hanshengchen97@gmail.com
"""

import sys
import time
import argparse
import subprocess
import threading
import numpy as np


class Logger(object):
    def __init__(self, logfile=None):
        self.stdout = sys.stdout
        self.log = open(logfile, 'a') if logfile is not None else None
        sys.stdout = self

    def __del__(self):
        sys.stdout = self.stdout
        if self.log is not None:
            self.log.close()

    def write(self, message):
        self.stdout.write(message)
        if self.log is not None:
            self.log.write(message)

    def flush(self):
        if self.log is not None:
            self.log.flush()


logger = Logger()


class CustomFormatter(argparse.HelpFormatter):
    """
    From https://stackoverflow.com/questions/23936145/python-argparse-help-message-disable-metavar-for-short-options
    """
    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar, = self._metavar_formatter(action, action.dest)(1)
            return metavar
        else:
            parts = []
            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            # change to
            #    -s, --long ARGS
            else:
                default = action.dest.upper()
                args_string = self._format_args(action, default)
                for option_string in action.option_strings:
                    # parts.append('%s %s' % (option_string, args_string))
                    parts.append('%s' % option_string)
                parts[-1] += ' %s' % args_string
            return ', '.join(parts)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Monitor and limit GPU power peak',
        formatter_class=lambda prog: CustomFormatter(prog, max_help_position=36))
    parser.add_argument('-i', '--id', help='GPU index')
    parser.add_argument('-o', '--out', metavar='FILE', help='Output log file')
    parser.add_argument(
        '-r', '--range', metavar='LOW,HIGH',
        help='Range of max total power specifying <releaseThreshold,limitThreshold> (e.g. 1500,1700)')
    parser.add_argument('-pl', '--power-limit', metavar='POWER',
                        help='GPU power cap (w). See nvidia-smi -h for details')
    parser.add_argument('-lgc', '--lock-gpu-clocks', metavar='LOW,HIGH',
                        help='Specifies <minGpuClock,maxGpuClock>, '
                             'input can also be a singular desired clock value. '
                             'See nvidia-smi -h for details')
    parser.add_argument('-t', '--time', metavar='TIME', default=1.0,
                        help='Time interval (sec). Default: 1.0')
    parser.add_argument(
        '-rc', '--release-count', metavar='N', default=10,
        help='Number of consecutive steps below the LOW threshold required for the release. Default: 10')
    parser.add_argument('-swl', '--start-with-limit',
                        action='store_true', help='Whether to enforce limit at startup')
    args = parser.parse_args()
    if args.range is not None:
        assert args.power_limit is not None or args.lock_gpu_clocks is not None, \
            '-pl or -lgc must be specified to enforce limit'
    return args


def output_parse(output):
    output = output.strip().split(',')
    dev_id = int(output[0])
    timestamp = int(output[2])
    power = int(output[3])
    return dev_id, timestamp, power


def enforce_limit(pl, lgc, dev_ids):
    if pl is not None:
        outputs = subprocess.run(
            ['nvidia-smi', '-pl', str(pl), '-i', ','.join([str(i) for i in dev_ids])],
            stdout=subprocess.PIPE, universal_newlines=True).stdout
        print(outputs)
    if lgc is not None:
        outputs = subprocess.run(
            ['nvidia-smi', '-lgc', str(lgc), '-i', ','.join([str(i) for i in dev_ids])],
            stdout=subprocess.PIPE, universal_newlines=True).stdout
        print(outputs)
    return


def release_limit(pl, lgc, dev_ids, max_power):
    if pl is not None:
        for dev_id_, max_power_ in zip(dev_ids, max_power):
            outputs = subprocess.run(
                ['nvidia-smi', '-pl', str(max_power_), '-i', str(dev_id_)],
                stdout=subprocess.PIPE, universal_newlines=True).stdout
            print(outputs)
    if lgc is not None:
        outputs = subprocess.run(
            ['nvidia-smi', '-rgc', '-i', ','.join([str(i) for i in dev_ids])],
            stdout=subprocess.PIPE, universal_newlines=True).stdout
        print('Reset clocks for GPU ' + ','.join([str(i) for i in dev_ids]))
        print(outputs)
    return


def timer_fun(dev_ids, power_logs, power_peaks, power_peak_times, interval, max_power,
              low=None, high=None, pl=None, lgc=None, release_count=10, start_with_limit=False):
    time.sleep(1.0)
    next_call = time.time()
    limit = False
    low_count = 0

    if start_with_limit:
        print('Enforcing limit at startup...')
        limit = True
        enforce_limit(pl, lgc, dev_ids)

    while True:
        now = time.strftime('%Y%m%d-%H-%M-%S')
        print(now + '   Limit enabled: {}'.format(limit))

        sum_avg = 0
        sum_max = 0
        for index_, (dev_id_, power_log) in enumerate(zip(
                dev_ids, power_logs)):

            power_log_interval, power_log[:] = power_log[:], []
            power_log_interval = np.array(power_log_interval)
            if len(power_log_interval):
                avg_pwr = np.mean(power_log_interval)
                max_pwr = np.max(power_log_interval)
            else:
                avg_pwr = 0
                max_pwr = 0

            sum_avg += avg_pwr
            sum_max += max_pwr

            if max_pwr > power_peaks[index_]:
                power_peaks[index_] = max_pwr
                power_peak_times[index_] = now

            print('GPU{:2d}   {}sAVG={:6.1f}w   {}sMAX={:6.1f}w   '
                  'PEAK={:6.1f}w @ {}'.format(
                      dev_id_, interval, avg_pwr, interval, max_pwr,
                      power_peaks[index_], power_peak_times[index_]))

        if sum_max > power_peaks[-1]:
            power_peaks[-1] = sum_max
            power_peak_times[-1] = now

        print('TOTAL   {}sAVG={:6.1f}w   {}sMAX={:6.1f}w   PEAK={:6.1f}w @ {}\n'.format(
            interval, sum_avg, interval, sum_max,
            power_peaks[-1], power_peak_times[-1]))

        if low is not None and high is not None:
            if not limit and sum_max >= high:
                limit = True
                enforce_limit(pl, lgc, dev_ids)
            if sum_max >= low:
                low_count = 0
            if limit and sum_max < low:
                low_count += 1
                if low_count >= release_count:
                    limit = False
                    release_limit(pl, lgc, dev_ids, max_power)

        next_call = next_call + interval
        time.sleep(max(next_call - time.time(), 0))


def main():
    args = parse_args()
    if args.range is not None:
        low, high = args.range.split(',')
        low = float(low)
        high = float(high)
        assert low < high, 'releaseThreshold must be less than limitThreshold'
    else:
        low = high = None
    if args.out is not None:
        global logger
        logger = Logger(args.out)

    command = ['nvidia-smi', 'stats', '-d', 'pwrDraw']
    if args.id is not None:
        command += ['-i', str(args.id)]

    # init
    dev_ids = []

    command_init = command + ['-c', '1']
    outputs = subprocess.run(command_init, stdout=subprocess.PIPE, universal_newlines=True).stdout
    for output in outputs.splitlines():
        dev_id, _, _ = output_parse(output)
        if dev_id not in dev_ids:
            dev_ids.append(dev_id)

    print('Device maximum power cap:')
    max_power = []
    for dev_id in dev_ids:
        outputs = subprocess.run(
            'nvidia-smi -q -i {} | grep "Max Power Limit"'.format(dev_id), shell=True,
            stdout=subprocess.PIPE, universal_newlines=True).stdout
        max_power_ = outputs.split(' ')[-2]
        max_power.append(max_power_)
        print('GPU{:2d}: {}w'.format(dev_id, max_power_))
    print()

    power_logs = [[] for _ in range(len(dev_ids))]
    power_peaks = [0 for _ in range(len(dev_ids) + 1)]
    power_peak_times = [time.strftime('%Y%m%d-%H-%M-%S') for _ in range(len(dev_ids) + 1)]

    # run
    process = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)

    timer = threading.Thread(
        target=timer_fun,
        args=(dev_ids, power_logs, power_peaks, power_peak_times, float(args.time), max_power,
              low, high, args.power_limit, args.lock_gpu_clocks, int(args.release_count),
              args.start_with_limit))
    timer.setDaemon(True)
    timer.start()

    try:
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                dev_id, _, power = output_parse(output)
                index = dev_ids.index(dev_id)
                power_logs[index].append(power)

    except KeyboardInterrupt:
        process.poll()

    return


if __name__ == '__main__':
    main()
