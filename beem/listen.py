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
This is a module for a single message consumption process
It listens to a topic and expects to see a known sequence of messages.
"""

from __future__ import division

import collections
import logging
import math
import random
import string
import time

import mosquitto

class MsgStatus():
    """
    Allows recording statistics of a published message.
    Used internally to generate statistics for the run.
    """
    def __key(self):
        # Yes, we only care about these.  This lets us find duplicates easily
        # TODO - perhaps time_created could go here too?
        return (self.cid, self.mid)

    def __init__(self, msg):
        segments = msg.topic.split("/")
        self.cid = segments[1]
        self.mid = int(segments[3])
        self.time_created = time.mktime(time.localtime(float(msg.payload)))
        self.time_received = time.time()

    def time_flight(self):
        return self.time_received - self.time_created

    def __repr__(self):
        return ("MSG(%s:%d) OK, flight time: %f ms (c:%f, r:%f)"
            % (self.cid, self.mid, self.time_flight() * 1000, self.time_created, self.time_received))

    def __eq__(x, y):
        return x.__key() == y.__key()

    def __hash__(self):
        return hash(self.__key())


class TrackingListener():
    """
    An MQTT message subscriber that tracks an expected message sequence
    This is a port of a very simplistic internal listener, needs a lot of work yet
    """
    msg_statuses = []
    def __init__(self, host, port, opts):
        self.options = opts
        self.cid = opts.clientid
        self.log = logging.getLogger(__name__ + ":" + self.cid)
        self.mqttc = mosquitto.Mosquitto(self.cid)
        self.mqttc.on_message = self.msg_handler
        self.listen_topic = opts.topic
        self.time_start = None
        # TODO - you _probably_ want to tweak this
        self.mqttc.max_inflight_messages_set(200)
        rc = self.mqttc.connect(host, port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how? 
        self.mqttc.loop_start()

    def msg_handler(self, mosq, userdata, msg):
        # WARNING: this _must_ release as quickly as possible!
        # get the sequence id from the topic, payload contains random garbage by default
        # TODO - we should change that!
        # get timing infomation in there to help with flight stats
        #self.log.debug("heard a message on topic: %s", msg.topic)
        if not self.time_start:
            self.time_start = time.time()
        ms = MsgStatus(msg)
        self.msg_statuses.append(ms)

    def run(self, qos=1):
        """
        Start a (long lived) process waiting for messages to arrive.
        The number of clients and messages per client that are expected
        are set at creation time

        """
        self.expected = self.options.msg_count * self.options.client_count
        self.log.info("Listening for %d messages on topic %s (q%d)",
            self.expected, self.listen_topic, qos)
        rc = self.mqttc.subscribe(self.listen_topic, qos)
        while len(self.msg_statuses) < self.expected:
            # let the mosquitto thread fill us up
            time.sleep(1)
            self.log.info("Still waiting for %d messages", self.expected - len(self.msg_statuses))
        self.time_end = time.time()

        self.mqttc.loop_stop()
        self.mqttc.disconnect()

    def stats(self):
        msg_count = len(self.msg_statuses)
        flight_times = [x.time_flight() for x in self.msg_statuses]
        mean = sum(flight_times) / len(flight_times)
        squares = [x * x for x in [q - mean for q in flight_times]]
        stddev = math.sqrt(sum(squares) / len(flight_times))

        actual_clients = set([x.cid for x in self.msg_statuses])
        per_client_expected = range(1, self.options.msg_count + 1)
        per_client_real = {}
        per_client_missing = {}
        for cid in actual_clients:
            per_client_real[cid] = [x.mid for x in self.msg_statuses if x.cid == cid]
            per_client_missing[cid] = list(set(per_client_expected).difference(set(per_client_real[cid])))

        return {
            "clientid": self.cid,
            "client_count": len(actual_clients),
            "msg_duplicates": [x for x,y in collections.Counter(self.msg_statuses).items() if y > 1],
            "msg_missing": per_client_missing,
            "msg_count": msg_count,
            "ms_per_msg": (self.time_end - self.time_start) / msg_count * 1000,
            "msg_per_sec": msg_count/(self.time_end - self.time_start),
            "time_total": self.time_end - self.time_start,
            "flight_time_mean": mean,
            "flight_time_stddev": stddev,
            "flight_time_max": max(flight_times),
            "flight_time_min": min(flight_times)
        }
