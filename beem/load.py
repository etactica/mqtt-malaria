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
This is a module for a single message publishing process.
It is capable of generating a stream of messages and collecting timing
statistics on the results of publishing that stream.
"""

from __future__ import division

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

class TrackingSender():
    """
    An MQTT message publisher that tracks time to ack publishes

    functions make_topic(sequence_num) and make_payload(sequence_num, size)
    can be provided to help steer message generation

    The timing of the publish calls are tracked for analysis

    This is a _single_ publisher, it's not a huge load testing thing by itself.

    Example:
      cid = "Test-clientid-%d" % os.getpid()
      ts = TrackingSender("mqtt.example.org", 1883, cid)
      ts.run(100, 1024)
      stats = ts.stats()
      print(stats["rate_ok"])
      print(stats["time_stddev"])
    """
    msg_statuses = {}
    def __init__(self, host, port, cid):
        self.cid = cid
        self.log = logging.getLogger(__name__ + ":" + cid)
        self.mqttc = mosquitto.Mosquitto(cid)
        self.mqttc.on_publish = self.publish_handler
        self.make_topic = None
        self.make_payload = None
        # TODO - you _probably_ want to tweak this
        if hasattr(self.mqttc, "max_inflight_messages_set"):
            self.mqttc.max_inflight_messages_set(200)
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
        """
        Default payload generator.
        Generates gaussian normal hex digits centered around msg_size
        The variance is msg_size/20
        """
        real_size = int(random.gauss(msg_size, msg_size / 20))
        msg = ''.join(random.choice(string.hexdigits) for x in range(real_size))
        return msg

    def _make_topic(self, msg_seq):
        if self.make_topic:
            return self.make_topic(msg_seq)
        else:
            return self._make_topic_default(msg_seq)

    def _make_topic_default(self, message_seq):
        """
        Default topic generator.
        Generates topics "mqtt-malaria/<clientid>/data/<message_sequence_number>"
        """
        return "mqtt-malaria/%s/data/%d" % (self.cid, message_seq)

    def publish_handler(self, mosq, userdata, mid):
        self.log.debug("Received confirmation of mid %d", mid)
        handle = self.msg_statuses.get(mid, None)
        while not handle:
            self.log.warn("Received a publish for mid: %d before we saved its creation", mid)
            time.sleep(0.5)
            handle = self.msg_statuses.get(mid, None)
        handle.receive()

    def run(self, msg_count, msg_size, qos=1):
        """
        Start a (long lived) process publishing msg_count messages
        of msg_size at the provided qos.
        if topic/payload generators are not provided, the default handlers
        are used.

        This process blocks until _all_ published messages have been acked by
        the publishing library.
        """
        for i in range(msg_count):
            payload = self._make_payload(i, msg_size)
            topic = self._make_topic(i)
            result, mid = self.mqttc.publish(topic, payload, qos)
            assert(result == 0)
            self.msg_statuses[mid] = MsgStatus(mid, len(payload))
        self.log.info("Finished publish %d msgs of %d bytes at qos %d", msg_count, msg_size, qos)

        finished = False
        while not finished:
            missing = [x for x in self.msg_statuses.values() if not x.received]
            finished = len(missing) == 0
            if finished:
                break
            self.log.info("Waiting for %d messages to be confirmed still...", len(missing))
            time.sleep(2) # This is too long for short tests.
            for x in missing:
                self.log.debug(x)
            # FIXME - needs an escape clause here for giving up on messages?

    def stats(self):
        """
        Generate a set of statistics for the set of message responses.
        count, success rate, min/max/mean/stddev are all generated.
        """
        successful = [x for x in self.msg_statuses.values() if x.received]
        rate = len(successful) / len(self.msg_statuses)
        # Let's work in milliseconds now
        times = [x.time_flight() * 1000 for x in successful]
        mean = sum(times) / len(times)
        squares = [x * x for x in [q - mean for q in times]]
        stddev = math.sqrt(sum(squares) / len(times))
        return {
            "clientid": self.cid,
            "count_ok": len(successful),
            "count_total": len(self.msg_statuses),
            "rate_ok" : rate,
            "time_mean" : mean,
            "time_min" : min(times),
            "time_max" : max(times),
            "time_stddev" : stddev
        }
        

