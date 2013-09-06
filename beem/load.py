#!/usr/bin/env python
"""
The MIT License

Copyright (c) 2013 ReMake Electric ehf

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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

class TrackingSender():
    """
    Creates a mqtt client and, on demand, publishes messages
    The timing of the publish calls are tracked for analysis
    """
    msg_statuses = {}
    def __init__(self, host, port, cid):
        self.cid = cid
        self.mqttc = mosquitto.Mosquitto(cid)
        self.mqttc.on_publish = self.publish_handler
        self.make_topic = None
        self.make_payload = None
        # TODO - you _may_ want to tweak this
        # self.mqttc.max_inflight_messages_set(yyyyy)
        rc = self.mqttc.connect(host, port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how? 
        self.mqttc.loop_start()

    def _make_payload(self, msg_seq, msg_size):
        if self.make_payload:
            return self.make_payload(msg_seq, msg_size)
        else:
            return self._make_payload_default(msg_size)
    
    def _make_payload_default(self, msg_size):
        real_size = int(random.gauss(msg_size, msg_size / 20))
        msg = ''.join(random.choice(string.hexdigits) for x in range(real_size))
        return msg

    def _make_topic(self, msg_seq):
        if self.make_topic:
            return self.make_topic(msg_seq)
        else:
            return self._make_topic_default(msg_seq)

    def _make_topic_default(self, message_seq):
        return "test/%s/data/%d" % (self.cid, message_seq)

    def publish_handler(self, mosq, userdata, mid):
        logging.debug("Received confirmation of mid %d", mid)
        self.msg_statuses[mid].receive()

    def run(self, msg_count, msg_size, qos=1):
        for i in range(msg_count):
            payload = self._make_payload(i, msg_size)
            topic = self._make_topic(i)
            result, mid = self.mqttc.publish(topic, payload, qos)
            assert(result == 0)
            self.msg_statuses[mid] = MsgStatus(mid, len(payload))
        logging.debug("Published %d msgs of (gaussian) %d bytes", msg_count, msg_size)

        finished = False
        while not finished:
            missing = [x for x in self.msg_statuses.values() if not x.received]
            finished = len(missing) == 0
            logging.info("Waiting for %d messages to be confirmed still...", len(missing))
            if finished:
                break
            time.sleep(2)
            for x in missing:
                logging.debug(x)
            # FIXME - needs an escape clause here for giving up on messages?

    def stats(self):
        successful = [x for x in self.msg_statuses.values() if x.received]
        logging.info("Success rate = %f%%", 100 * (len(successful) / len(self.msg_statuses)))
        # Let's work in milliseconds now
        times = [x.time_flight() * 1000 for x in successful]
        mean = sum(times) / len(times)
        logging.info("Average flight time of successful messages = %f milliseconds", mean)
        squares = [x * x for x in [q - mean for q in times]]
        stddev = math.sqrt(sum(squares) / len(times))
        logging.info("Min / Max / StdDev flight times= %f / %f / %f milliseconds", min(times), max(times), stddev)
        

