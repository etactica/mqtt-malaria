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
import socket
import time

import beem
import beem.load
import beem.bridge
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

def worker(options, proc_num, auth=None):
    """
    Wrapper to run a test and push the results back onto a queue.
    Modify this to provide custom message generation routines.
    """
    # Make a new clientid with our worker process number
    cid = "%s-%d" % (options.clientid, proc_num)
    if options.bridge:
        ts = beem.bridge.BridgingSender(options.host, options.port, cid, auth)
        # This is _probably_ what you want if you are specifying a key file
        # This would correspond with using ids as clientids, and acls
        if auth:
            cid = auth.split(":")[0]
    else:
        ts = beem.load.TrackingSender(options.host, options.port, cid, auth)

    msg_generator = beem.msgs.GaussianSize(cid, options.msg_count, options.msg_size)
    if options.timing:
        msg_generator = beem.msgs.TimeTracking(msg_generator)
    if options.msgs_per_second > 0:
        msg_generator = beem.msgs.RateLimited(msg_generator, options.msgs_per_second)
    # Provide a custom generator
    #msg_generator = my_custom_msg_generator(options.msg_count)
    # This helps introduce jitter so you don't have many threads all in sync
    time.sleep(random.uniform(0,3))
    ts.run(msg_generator, qos=options.qos)
    return ts.stats()


def add_args(subparsers):
    parser = subparsers.add_parser(
        "publish",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__,
        help="Publish a stream of messages")

    parser.add_argument(
        "-c", "--clientid",
        default="beem.loadr-%s-%d" % (socket.gethostname(), os.getpid()),
        help="""Set the client id of the publisher, can be useful for acls.
        Default includes host and pid information, unless a keyfile was
        specified, in which case the "user/identity" part is used as the
        client id.  The clientid is also used in the default topics.
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
        hex characters.  This can be combined with --msg-size option""")
    parser.add_argument(
        "-T", "--msgs_per_second", type=float, default=0,
        help="""Each publisher should target sending this many msgs per second,
        useful for simulating real devices.""")

    parser.add_argument(
        "-b", "--bridge", action="store_true",
        help="""Instead of connecting directly to the target, fire up a 
        separate mosquitto instance configured to bridge to the target""")
    proc_count_group = parser.add_mutually_exclusive_group()
    proc_count_group.add_argument(
        "-P", "--processes", type=int, default=1,
        help="How many separate processes to spin up (multiprocessing)")

    proc_count_group.add_argument(
        "--bridge_psk_file", type=argparse.FileType("r"),
        help="""A file of psk 'identity:key' pairs, as you would pass to
mosquitto's psk_file configuration option.  A bridge will be created for
each line in the file. (Cannot be used with --processes, obviously).""")

    parser.set_defaults(handler=run)


def run(options):
    # If we're bridging, and have a key file, 
    if options.bridge_psk_file:
        print("Operating with a psk file: %s" % options.bridge_psk_file)
        auth_pairs = options.bridge_psk_file.readlines()
        options.processes = len(auth_pairs)

    pool = multiprocessing.Pool(processes=options.processes)
    time_start = time.time()
    # This should be pretty easy to use for passwords as well as PSK....
    if auth_pairs:
        result_set = [pool.apply_async(worker, (options, x, auth.strip())) for x,auth in enumerate(auth_pairs)]
    else:
        result_set = [pool.apply_async(worker, (options, x)) for x in range(options.processes)]
    remaining = options.processes

    completed_set = []
    while len(completed_set) < options.processes:
        hold_set = []
        for result in result_set:
            if result.ready():
                completed_set.append(result)
            else:
                hold_set.append(result)
        result_set = hold_set
        print("Completed workers: %d/%d" % (len(completed_set), options.processes))
        if len(result_set) > 0:
            time.sleep(1)

    time_end = time.time()
    stats_set = []
    for result in completed_set:
        s = result.get()
        beem.print_publish_stats(s)
        stats_set.append(s)

    agg_stats = beem.aggregate_publish_stats(stats_set)
    agg_stats["time_total"] = time_end - time_start
    beem.print_publish_stats(agg_stats)
