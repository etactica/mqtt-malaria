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
# This file implements the "malaria subscribe" command
"""
Listen to a stream of messages and capture statistics on their timing
"""

import argparse
import os
import beem.listen

def print_stats(stats):
    """
    pretty print a listen stats object
    """
    print("Clientid: %s" % stats["clientid"])
    print("Total clients tracked: %s" % stats["client_count"])
    print("Total messages: %d" % stats["msg_count"])
    print("Total time: %0.2f secs" % stats["time_total"])
    print("Messages per second: %d (%f ms per message)"
        % (stats["msg_per_sec"], stats["ms_per_msg"]))
    if stats["test_complete"]:
        for cid,dataset in stats["msg_missing"].items():
            if len(dataset) > 0:
                print("Messages missing for client %s: %s" % (cid, dataset))
        print("Messages duplicated: %s" % stats["msg_duplicates"])
    else:
        print("Test aborted, unable to gather duplicate/missing stats")
    print("Flight time mean:   %0.2f ms" % (stats["flight_time_mean"] * 1000))
    print("Flight time stddev: %0.2f ms" % (stats["flight_time_stddev"] * 1000))
    print("Flight time min:    %0.2f ms" % (stats["flight_time_min"] * 1000))
    print("Flight time max:    %0.2f ms" % (stats["flight_time_max"] * 1000))


def add_args(subparsers):
    parser = subparsers.add_parser(
        "subscribe",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__,
        help="Listen to a stream of messages")

    parser.add_argument(
        "-c", "--clientid", default="beem.listr-%d" % os.getpid(),
        help="""Set the client id of the listner, can be useful for acls
        Default has pid information appended.
        """)
    parser.add_argument(
        "-H", "--host", default="localhost",
        help="MQTT host to connect to")
    parser.add_argument(
        "-p", "--port", type=int, default=1883,
        help="Port for remote MQTT host")
    parser.add_argument(
        "-q", "--qos", type=int, choices=[0, 1, 2],
        help="set the mqtt qos for subscription", default=1)
    parser.add_argument(
        "-n", "--msg_count", type=int, default=10,
        help="How many messages to expect")
    parser.add_argument(
        "-N", "--client_count", type=int, default=1,
        help="""How many clients to expect. See docs for examples
        of how this works""")
    parser.add_argument(
        "-t", "--topic", default="mqtt-malaria/+/data/#",
        help="""Topic to subscribe to, will be sorted into clients by the
         '+' symbol""")

    parser.set_defaults(handler=run)


def run(options):
    ts = beem.listen.TrackingListener(options.host, options.port, options)
    ts.run(options.qos)
    print_stats(ts.stats())
