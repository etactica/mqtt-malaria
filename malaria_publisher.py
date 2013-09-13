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
"""
An application capable of running multiple mqtt message publishing processes
to help with load testing or scalability testing or just to provide a stream
of messages.
"""

import argparse
import logging
import multiprocessing
import os
import beem
import beem.load

logging.basicConfig(level=logging.INFO)

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
    # Provide a custom generator
    #msg_generator = my_custom_msg_generator(options.msg_count)
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

def aggregate_stats(stats_set):
    """
    For a set of per process stats, make some basic aggregated stats
    timings are a simple mean of the input timings. ie the aggregate
    "minimum" is the average of the minimum of each process, not the
    absolute minimum of any process.
    Likewise, aggregate "stddev" is a simple mean of the stddev from each
    process, not an entire population stddev.
    """
    mins = [x["time_min"] for x in stats_set]
    maxes = [x["time_max"] for x in stats_set]
    means = [x["time_mean"] for x in stats_set]
    stddevs = [x["time_stddev"] for x in stats_set]
    count_ok = sum([x["count_ok"] for x in stats_set])
    count_total = sum([x["count_total"] for x in stats_set])
    cid = "Aggregate stats (simple avg) for %d processes" % len(stats_set)
    return {
        "clientid": cid,
        "count_ok": count_ok,
        "count_total": count_total,
        "rate_ok": count_ok / count_total,
        "time_min": sum(mins) / len(mins),
        "time_max": sum(maxes) / len(maxes),
        "time_mean": sum(means) / len(means),
        "time_stddev": sum(stddevs) / len(stddevs)
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        Publish a stream of messages and capture statistics on their timing
        """)

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
        "-P", "--processes", type=int, default=1,
        help="How many separate processes to spin up (multiprocessing)")

    options = parser.parse_args()

    pool = multiprocessing.Pool(processes=options.processes)
    result_set = [pool.apply_async(worker, (options, x)) for x in range(options.processes)]
    remaining = options.processes

    stats_set = []
    while remaining > 0:
        print("Still waiting for results from %d process(es)" % remaining)
        try:
            # This will print results in order started, not order completed :|
            for result in result_set:
                s = result.get(timeout=0.5)
                remaining -= 1
                print_stats(s)
                stats_set.append(s)
        except multiprocessing.TimeoutError:
            pass

    agg_stats = aggregate_stats(stats_set)
    print_stats(agg_stats)


if __name__ == "__main__":
    main()
