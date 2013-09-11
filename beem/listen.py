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
    def __init__(self, mid, real_size):
        self.mid = mid
        self.size = real_size
        self.received = False
        self.time_created = time.time()
        self.time_received = None

    def receive(self):
        self.received = True
        self.time_received = time.time()

    def time_flight(self):
        return self.time_received - self.time_created

    def __repr__(self):
        if self.received:
            return ("MSG(%d) OK, flight time: %f seconds" % (self.mid, self.time_flight()))
        else:
            return ("MSG(%d) INCOMPLETE in flight for %f seconds so far"
                % (self.mid, time.time() - self.time_created))

class TrackingListener():
    """
    An MQTT message subscriber that tracks an expected message sequence
    This is a port of a very simplistic internal listener, needs a lot of work yet
    """
    msg_statuses = {}
    def __init__(self, host, port, opts):
        self.options = opts
        self.cid = opts.clientid
        self.log = logging.getLogger(__name__ + ":" + self.cid)
        self.mqttc = mosquitto.Mosquitto(self.cid)
        self.mqttc.on_message = self.msg_handler
        self.listen_topic = opts.topic
        self.rxids = []
        # TODO - you _probably_ want to tweak this
        self.mqttc.max_inflight_messages_set(200)
        rc = self.mqttc.connect(host, port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how? 
        self.mqttc.loop_start()

    def msg_handler(self, mosq, userdata, msg):
        # get the sequence id from the topic, payload contains random garbage by default
        # TODO - we should change that!
        # get timing infomation in there to help with flight stats
        self.log.debug("heard a message on topic: %s", msg.topic)
        segments = msg.topic.split("/")
        sequence = segments[-1]
        self.rxids.append(int(sequence))

    def run(self, msg_count, qos=1):
        """
        Start a (long lived) process waiting for the specified number of
        messages to arrive.

        if topic/payload generators are not provided, the default handlers
        are used.

        This process blocks until _all_ published messages have been acked by
        the publishing library.
        """
        self.expected_count = msg_count
        self.log.info("Listening for %d messages on topic %s (q%d)",
            msg_count, self.listen_topic, qos)
        rc = self.mqttc.subscribe(self.listen_topic, qos)
        self.time_start = time.time()
        while len(self.rxids) < msg_count:
            # let the mosquitto thread fill us up
            time.sleep(1)
            self.log.info("Still waiting for %d messages", msg_count - len(self.rxids))
        self.time_end = time.time()

        self.mqttc.loop_stop()
        self.mqttc.disconnect()

    def stats(self):
        expected = set(range(self.expected_count))
        msg_count = len(self.rxids)
        return {
            "clientid": self.cid,
            "msg_duplicates": [x for x,y in collections.Counter(self.rxids).items() if y > 1],
            "msg_missing": [x for x in sorted(expected.difference(set(self.rxids)))],
            "msg_count": msg_count,
            "ms_per_msg": (self.time_end - self.time_start) / msg_count * 1000,
            "msg_per_sec": msg_count/(self.time_end - self.time_start)
        }
