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
import time

import paho.mqtt.client as mqtt

from beem.trackers import SentMessage as MsgStatus


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
      generator = beem.msgs.GaussianSize(cid, 100, 1024)
      ts.run(generator, qos=1)
      stats = ts.stats()
      print(stats["rate_ok"])
      print(stats["time_stddev"])
    """
    msg_statuses = {}

    def __init__(self, host, port, cid):
        self.cid = cid
        self.log = logging.getLogger(__name__ + ":" + cid)
        self.mqttc = mqtt.Client(cid)
        self.mqttc.on_publish = self.publish_handler
        # TODO - you _probably_ want to tweak this
        if hasattr(self.mqttc, "max_inflight_messages_set"):
            self.mqttc.max_inflight_messages_set(200)
        rc = self.mqttc.connect(host, port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how?
        self.mqttc.loop_start()

    def publish_handler(self, mosq, userdata, mid):
        self.log.debug("Received confirmation of mid %d", mid)
        handle = self.msg_statuses.get(mid, None)
        while not handle:
            self.log.warn("Received a publish for mid: %d before we saved its creation", mid)
            time.sleep(0.5)
            handle = self.msg_statuses.get(mid, None)
        handle.receive()

    def run(self, msg_generator, qos=1):
        """
        Start a (long lived) process publishing messages
        from the provided generator at the requested qos

        This process blocks until _all_ published messages have been acked by
        the publishing library.
        """
        publish_count = 0
        self.time_start = time.time()
        for _, topic, payload in msg_generator:
            result, mid = self.mqttc.publish(topic, payload, qos)
            assert(result == 0)
            self.msg_statuses[mid] = MsgStatus(mid, len(payload))
            publish_count += 1
        self.log.info("Finished publish %d msgs at qos %d", publish_count, qos)

        finished = False
        while not finished:
            missing = [x for x in self.msg_statuses.values() if not x.received]
            finished = len(missing) == 0
            if finished:
                break
            mc = len(missing)
            self.log.info("Still waiting for %d messages to be confirmed.", mc)
            time.sleep(2)  # This is too long for short tests.
            for x in missing:
                self.log.debug(x)
            # FIXME - needs an escape clause here for giving up on messages?
        self.time_end = time.time()
        self.mqttc.loop_stop()
        time.sleep(1)
        self.mqttc.disconnect()

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
            "rate_ok": rate,
            "time_mean": mean,
            "time_min": min(times),
            "time_max": max(times),
            "time_stddev": stddev,
            "msgs_per_sec": len(successful) / (self.time_end - self.time_start),
            "time_total": self.time_end - self.time_start
        }
