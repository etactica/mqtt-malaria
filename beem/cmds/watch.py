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
# This file implements the "malaria watch" command
"""
Listen to a stream of messages and passively collect long term stats
"""

import argparse
import os
import beem.listen


def add_args(subparsers):
    parser = subparsers.add_parser(
        "watch",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__,
        help="Idly watch a stream of messages go past")

    parser.add_argument(
        "-c", "--clientid", default="beem.watchr-%d" % os.getpid(),
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
        "-t", "--topic", default=[], action="append",
        help="""Topic to subscribe to, will be sorted into clients by the
         '+' symbol if available. Will actually default to "#" if no custom
         topics are provided""")
    parser.add_argument(
        "-d", "--directory", help="Directory to publish statistics FS to")

    parser.set_defaults(handler=run)


def run(options):
    if not len(options.topic):
        options.topic = ["#"]
    beem.listen.CensusListener(options)
