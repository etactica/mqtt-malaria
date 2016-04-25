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
import errno
import logging
import math
import os
import stat
import tempfile
import time

import fuse
import paho.mqtt.client as mqtt

from beem.trackers import ObservedMessage as MsgStatus


class TrackingListener():
    """
    An MQTT message subscriber that tracks an expected message sequence
    and generates timing, duplicate/missing and monitors for drops
    """

    msg_statuses = []

    def __init__(self, host, port, opts):
        self.options = opts
        self.cid = opts.clientid
        self.log = logging.getLogger(__name__ + ":" + self.cid)
        self.mqttc = mqtt.Client(self.cid)
        self.mqttc.on_message = self.msg_handler
        self.listen_topic = opts.topic
        self.time_start = None
        # TODO - you _probably_ want to tweak this
        self.mqttc.max_inflight_messages_set(200)
        rc = self.mqttc.connect(host, port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how?
        self.mqttc.subscribe('$SYS/broker/publish/messages/dropped', 0)
        self.drop_count = None
        self.dropping = False
        self.mqttc.loop_start()

    def msg_handler(self, mosq, userdata, msg):
        # WARNING: this _must_ release as quickly as possible!
        # get the sequence id from the topic
        #self.log.debug("heard a message on topic: %s", msg.topic)
        if msg.topic == '$SYS/broker/publish/messages/dropped':
            if self.drop_count:
                self.log.warn("Drop count has increased by %d",
                              int(msg.payload) - self.drop_count)
                self.dropping = True
            else:
                self.drop_count = int(msg.payload)
                self.log.debug("Initial drop count: %d", self.drop_count)
            return
        if not self.time_start:
            self.time_start = time.time()

        try:
            ms = MsgStatus(msg)
            self.msg_statuses.append(ms)
        except Exception:
            self.log.exception("Failed to parse a received message. (Is the publisher sending time-tracking information with -t?)")

    def run(self, qos=1):
        """
        Start a (long lived) process waiting for messages to arrive.
        The number of clients and messages per client that are expected
        are set at creation time

        """
        self.expected = self.options.msg_count * self.options.client_count
        self.log.info(
            "Listening for %d messages on topic %s (q%d)",
            self.expected, self.listen_topic, qos)
        rc = self.mqttc.subscribe(self.listen_topic, qos)
        #assert rc == 0, "Failed to subscribe?! this isn't handled!", rc
        while len(self.msg_statuses) < self.expected:
            # let the mosquitto thread fill us up
            time.sleep(1)
            self.log.info("Still waiting for %d messages",
                          self.expected - len(self.msg_statuses))
            if self.dropping:
                self.log.error("Detected drops are occuring, aborting test!")
                break
        self.time_end = time.time()
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
            "test_complete": not self.dropping,
            "msg_duplicates": [x for x, y in collections.Counter(self.msg_statuses).items() if y > 1],
            "msg_missing": per_client_missing,
            "msg_count": msg_count,
            "ms_per_msg": (self.time_end - self.time_start) / msg_count * 1000,
            "msg_per_sec": msg_count / (self.time_end - self.time_start),
            "time_total": self.time_end - self.time_start,
            "flight_time_mean": mean,
            "flight_time_stddev": stddev,
            "flight_time_max": max(flight_times),
            "flight_time_min": min(flight_times)
        }


def static_file_attrs(content=None):
    now = time.time()
    if content:
        size = len(content)
    else:
        size = 20
    return {
            "file": dict(st_mode=(stat.S_IFREG | 0444), st_nlink=1,
                            st_size=size,
                            st_ctime=now, st_mtime=now,
                            st_atime=now),
            "content": content
            }


class MalariaWatcherStatsFS(fuse.LoggingMixIn, fuse.Operations):

    file_attrs = dict(st_mode=(stat.S_IFREG | 0444), st_nlink=1,
                            st_size=20000,
                            st_ctime=time.time(), st_mtime=time.time(),
                            st_atime=time.time())

    dir_attrs = dict(st_mode=(stat.S_IFDIR | 0755),  st_nlink=2,
                            st_ctime=time.time(), st_mtime=time.time(),
                            st_atime=time.time())
    README_STATFS = """
This is a FUSE filesystem that contains a set of files representing various
statistics we have gathered about the MQTT broker we are watching and the
topics we are subscribed to.
"""
    msgs_total = 0
    msgs_stored = 0
    drop_count = 0
    drop_count_initial = None

    def handle_msgs_total(self):
        """Total number of messages seen since we started"""
        return self.msgs_total

    def handle_msgs_stored(self):
        """Total number of stored ($sys/broker/messages/stored)"""
        return self.msgs_stored

    def handle_uptime(self):
        """Time in seconds this watcher has been running"""
        return time.time() - self.time_start

    def handle_drop_count(self):
        """Total drops since this watcher has been running"""
        return self.drop_count

    def handle_topic(self):
        """The topics this watcher is subscribing too"""
        return '\n'.join(self.listen_topics)

    def handle_readme(self):
        """Returns 'this' readme ;)"""
        rval = self.README_STATFS
        useful = [x for x in self.handlers if x != '/']
        file_field = "File                   "
        rval += "\n" + file_field + "Description\n\n"
        for h in useful:
            func = self.handlers[h].get("handler", None)
            desc = None
            if not func:
                desc = "Raw file, no further description"
            if func:
                desc = func.__doc__
            if not desc:
                desc = "No description in handler method! (Fix pydoc!)"
            # pad file line to line up with the description
            line = "%s%s\n" % (str.ljust(h[1:], len(file_field)), desc)
            rval += line
        return rval

    handlers = {
            "/": {"file": dir_attrs, "handler": None},
            "/msgs_total": {"file": file_attrs, "handler": handle_msgs_total},
            "/msgs_stored": {"file": file_attrs, "handler": handle_msgs_stored},
            "/uptime": {"file": file_attrs, "handler": handle_uptime},
            "/topic": {"file": file_attrs, "handler": handle_topic},
            "/drop_count": {"file": file_attrs, "handler": handle_drop_count},
            "/README": static_file_attrs(README_STATFS),
            "/README.detailed": {"file": file_attrs, "handler": handle_readme}
        }

    def __init__(self, options):
        print("listener operations __init__")
        self.options = options
        self.time_start = time.time()

    def msg_handler(self, mosq, userdata, msg):
        # WARNING: this _must_ release as quickly as possible!
        # get the sequence id from the topic
        #self.log.debug("heard a message on topic: %s", msg.topic)
        if "/messages/dropped" in msg.topic:
            if self.drop_count_initial:
                self.log.warn("Drop count has increased by %d",
                              (int(msg.payload) - self.drop_count_initial))
                self.drop_count = int(msg.payload) - self.drop_count_initial
            else:
                self.drop_count_initial = int(msg.payload)
                self.log.debug("Initial drops: %d", self.drop_count_initial)
            return
        if "messages/stored" in msg.topic:
            self.msgs_stored = int(msg.payload)
            return
        self.msgs_total += 1

    def init(self, path):
        """
        Fuse calls this when it's ready, so we can start our actual mqtt
        processes here.
        """
        print("listener post init init(), path=", path)
        self.cid = self.options.clientid
        self.log = logging.getLogger(__name__ + ":" + self.cid)
        self.mqttc = mqtt.Client(self.cid)
        self.mqttc.on_message = self.msg_handler
        self.listen_topics = self.options.topic
        # TODO - you _probably_ want to tweak this
        self.mqttc.max_inflight_messages_set(200)
        rc = self.mqttc.connect(self.options.host, self.options.port, 60)
        if rc:
            raise Exception("Couldn't even connect! ouch! rc=%d" % rc)
            # umm, how?
        # b/p/m for >= 1.2, b/m for 1.1.x
        self.mqttc.subscribe('$SYS/broker/publish/messages/dropped', 0)
        self.mqttc.subscribe('$SYS/broker/messages/dropped', 0)
        self.mqttc.subscribe('$SYS/broker/messages/stored', 0)
        self.mqttc.loop_start()
        [self.mqttc.subscribe(t, self.options.qos) for t in self.listen_topics]

    def getattr(self, path, fh=None):
        if path not in self.handlers:
            raise fuse.FuseOSError(errno.ENOENT)

        return self.handlers[path]["file"]

    def read(self, path, size, offset, fh):
        if self.handlers[path].get("content", False):
            return self.handlers[path]["content"]
        funcy = self.handlers[path]["handler"]
        return str(funcy(self)) + "\n"

    def readdir(self, path, fh):
        return ['.', '..'] + [x[1:] for x in self.handlers if x != '/']


class CensusListener():
    """
    Create a listener that just watches all the messages go past.
    It doesn't care about time in flight or expected vs actual, it just cares
    about what it has seen, and maintains long term stats on whatever
    it does see.
    """
    def __init__(self, options):
        self.log = logging.getLogger(__name__)
        path_provided = True
        if not options.directory:
            path_provided = False
            options.directory = tempfile.mkdtemp()
        self.log.info("Statistics files will be available in %s", options.directory)
        fuse.FUSE(MalariaWatcherStatsFS(options),
                  options.directory, foreground=True)
        if not path_provided:
            self.log.info("Automatically removing statsfs: %s", options.directory)
            os.rmdir(options.directory)
