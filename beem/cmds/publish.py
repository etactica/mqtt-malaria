#!/usr/bin/env python
#
# Copyright (c) 2013, ReMake Electric ehf
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# This file implements the "malaria publish" command
"""
Publish a stream of messages and capture statistics on their timing.
"""

import argparse
import multiprocessing
import os
import random
import time

import beem
import beem.load
import beem.msgs

def my_custom_msg_generator(sequence_length):
    """
    An example of a custom msg generator.

    You must return a tuple of sequence number, topic and payload
    on each iteration.
    """
    seq = 0
    while seq < sequence_length:
        yield (seq, "magic_topic", "very boring payload")
        seq+=1

def worker(options, proc_num):
    """
    Wrapper to run a test and push the results back onto a queue.
    Modify this to provide custom message generation routines.
    """
    # Make a new clientid with our worker process number
    cid = "%s-%d" % (options.clientid, proc_num)
    ts = beem.load.TrackingSender(options.host, options.port, cid)
    msg_generator = None
    if options.timing:
        msg_generator = beem.msgs.TimeTracking(cid, options.msg_count)
    else:
        msg_generator = beem.msgs.GaussianSize(cid, options.msg_count, options.msg_size)

    if options.msgs_per_second > 0:
        msg_generator = beem.msgs.RateLimited(msg_generator, options.msgs_per_second)
    # Provide a custom generator
    #msg_generator = my_custom_msg_generator(options.msg_count)
    # This helps introduce jitter so you don't have many threads all in sync
    time.sleep(random.uniform(0,3))
    ts.run(msg_generator, qos=options.qos)
    return ts.stats()


def print_stats(stats):
    """
    pretty print a stats object
    """
    print("Clientid: %s" % stats["clientid"])
    print("Message succes rate: %.2f%% (%d/%d messages)"
        % (100 * stats["rate_ok"], stats["count_ok"], stats["count_total"]))
    print("Message timing mean   %.2f ms" % stats["time_mean"])
    print("Message timing stddev %.2f ms" % stats["time_stddev"])
    print("Message timing min    %.2f ms" % stats["time_min"])
    print("Message timing max    %.2f ms" % stats["time_max"])
    print("Messages per second   %.2f" % stats["msgs_per_sec"])
    print("Total time            %.2f secs" % stats["time_total"])

def aggregate_stats(stats_set):
    """
    For a set of per process stats, make some basic aggregated stats
    timings are a simple mean of the input timings. ie the aggregate
    "minimum" is the average of the minimum of each process, not the
    absolute minimum of any process.
    Likewise, aggregate "stddev" is a simple mean of the stddev from each
    process, not an entire population stddev.
    """
    def naive_average(the_set):
        return sum(the_set) / len(the_set)
    count_ok = sum([x["count_ok"] for x in stats_set])
    count_total = sum([x["count_total"] for x in stats_set])
    cid = "Aggregate stats (simple avg) for %d processes" % len(stats_set)
    return {
        "clientid": cid,
        "count_ok": count_ok,
        "count_total": count_total,
        "rate_ok": count_ok / count_total,
        "time_min": naive_average([x["time_min"] for x in stats_set]),
        "time_max": naive_average([x["time_max"] for x in stats_set]),
        "time_mean": naive_average([x["time_mean"] for x in stats_set]),
        "time_stddev": naive_average([x["time_stddev"] for x in stats_set]),
        "msgs_per_sec": naive_average([x["msgs_per_sec"] for x in stats_set]),
    }


def add_args(subparsers):
    parser = subparsers.add_parser(
        "publish",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__,
        help="Publish a stream of messages")

    parser.add_argument(
        "-c", "--clientid", default="beem.loadr-%d" % os.getpid(),
        help="""Set the client id of the publisher, can be useful for acls
        Default has pid information appended
        """)
    parser.add_argument(
        "-H", "--host", default="localhost",
        help="MQTT host to connect to")
    parser.add_argument(
        "-p", "--port", type=int, default=1883,
        help="Port for remote MQTT host")
    parser.add_argument(
        "-q", "--qos", type=int, choices=[0, 1, 2],
        help="set the mqtt qos for messages published", default=1)
    parser.add_argument(
        "-n", "--msg_count", type=int, default=10,
        help="How many messages to send")
    parser.add_argument(
        "-s", "--msg_size", type=int, default=100,
        help="Size of messages to send. This will be gaussian at (x, x/20)")
    parser.add_argument(
        "-t", "--timing", action="store_true",
        help="""Message bodies will contain timing information instead of random
        hex characters.  This overrides the --msg-size option, obviously""")
    parser.add_argument(
        "-T", "--msgs_per_second", type=float, default=0,
        help="""Each publisher should target sending this many msgs per second,
        useful for simulating real devices.""")
    parser.add_argument(
        "-P", "--processes", type=int, default=1,
        help="How many separate processes to spin up (multiprocessing)")

    parser.set_defaults(handler=run)


def run(options):
    pool = multiprocessing.Pool(processes=options.processes)
    time_start = time.time()
    result_set = [pool.apply_async(worker, (options, x)) for x in range(options.processes)]
    remaining = options.processes

    stats_set = []
    completed = 0
    while completed < options.processes:
        for result in result_set:
            if result.ready():
                completed += 1
        print("Completed workers: %d/%d" % (completed, options.processes))
        time.sleep(1)

    time_end = time.time()
    for result in result_set:
        s = result.get()
        print_stats(s)
        stats_set.append(s)

    agg_stats = aggregate_stats(stats_set)
    agg_stats["time_total"] = time_end - time_start
    print_stats(agg_stats)
