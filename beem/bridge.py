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
This is a module for a single message publishing process,
that publishes to it's own private bridge. The _bridge_ is configured
to bridge out to the designated target.
"""

from __future__ import division

import logging
import os
import socket
import subprocess
import tempfile
import threading
import time

import beem.load
import beem.msgs

MOSQ_BRIDGE_CFG_TEMPLATE = """
log_dest topic
#log_dest stdout
bind_address 127.0.0.1
port %(listen_port)d

connection mal-bridge-%(cid)s
address %(malaria_target)s
topic mqtt-malaria/# out %(qos)d
"""

MOSQ_BRIDGE_CFG_TEMPLATE_PSK = """
bridge_identity %(psk_id)s
bridge_psk %(psk_key)s
bridge_tls_version tlsv1
"""


class BridgingSender():
    """
    A MQTT message publisher that publishes to it's own personal bridge
    """
    def __init__(self, target_host, target_port, cid, auth=None):
        self.cid = cid
        self.auth = auth
        self.log = logging.getLogger(__name__ + ":" + cid)

        self.mb = MosquittoBridgeBroker(target_host, target_port, cid, auth)

    def run(self, generator, qos=1):
        with self.mb as mb:
            launched = False
            while not launched:
                try:
                    self.ts = beem.load.TrackingSender("localhost", mb.port, "ts_" + mb.label)
                    launched = True
                except:
                    # TrackingSender fails if it can't connect
                    time.sleep(0.5)
            self.ts.run(generator, qos)

    def stats(self):
        return self.ts.stats()


class _ThreadedBridgeWorker(threading.Thread):
    def __init__(self, mb, options):
        threading.Thread.__init__(self)
        self.mb = mb
        self.options = options

    def run(self):
        with self.mb as mb:
            launched = False
            while not launched:
                try:
                    ts = beem.load.TrackingSender("localhost", mb.port, "ts_" + mb.label)
                    launched = True
                except:
                    # TrackingSender fails if it can't connect
                    time.sleep(0.5)

            # This is probably what you want for psk setups with ACLs
            if self.mb.auth:
                cid = self.mb.auth.split(":")[0]
                gen = beem.msgs.createGenerator(cid, self.options)
            else:
                gen = beem.msgs.createGenerator(self.mb.label, self.options)
            ts.run(gen)
            self.stats = ts.stats()


class ThreadedBridgingSender():
    """
    A MQTT message publisher that publishes to it's own personal bridge,
    unlike BridgingSender, this fires up X brokers, and X threads to publish.
    This _can_ be much softer on memory usage, and as long as the per thread
    message rate stays low enough, and the ratio not too unreasonable, there
    should be no performance problems
    """

    def __init__(self, options, proc_num, auth=None):
        """
        target_host and target_port are used as is
        cid is used as cid_%d where the thread number is inserted
        auth should be an array of "identity:key" strings, of the same size as
        ratio
        """
        self.options = options
        self.cid_base = options.clientid
        self.auth = auth
        self.ratio = options.thread_ratio
        self.mosqs = []
        if auth:
            assert len(auth) == self.ratio
        self.log = logging.getLogger(__name__ + ":" + self.cid_base)

        # Create all the config files immediately
        for x in range(self.ratio):
            label = "%s_%d_%d" % (self.cid_base, proc_num, x)
            mb = MosquittoBridgeBroker(options.host,
                                             options.port,
                                             label)
            if auth:
                mb.auth = auth[x].strip()
            self.mosqs.append(mb)

    def run(self):
        worker_threads = []
        for mb in self.mosqs:
            t = _ThreadedBridgeWorker(mb, self.options)
            t.start()
            worker_threads.append(t)

        # Wait for all threads to complete
        self.stats = []
        for t in worker_threads:
            t.join()
            self.stats.append(t.stats)
            self.log.debug("stats were %s", t.stats)


class MosquittoBridgeBroker():
    """
    Runs an external mosquitto process configured to bridge to the target
    host/port, optionally with tls-psk.

    use this with a context manager to start/stop the broker automatically

        mm = MosquittoBridgeBroker(host, port, "my connection label",
                                   "psk_identity:psk_key")
        with mm as b:
            post_messages_to_broker(b.port)

    """

    def _get_free_listen_port(self):
        """
        Find a free local TCP port that we can listen on,
        we want this to be able to give to mosquitto.
        """
        # python 2.x doesn't have __enter__ and __exit__ on socket objects
        # so can't use with: clauses
        # Yes, there is a race condition between closing the socket and
        # starting mosquitto.
        s = socket.socket()
        s.bind(("localhost", 0))
        chosen_port = s.getsockname()[1]
        s.close()
        return chosen_port

    def _make_config(self):
        """
        Make an appropriate mosquitto config snippet out of
        our params and saved state
        """
        self.port = self._get_free_listen_port()
        template = MOSQ_BRIDGE_CFG_TEMPLATE
        inputs = {
            "listen_port": self.port,
            "malaria_target": "%s:%d" % (self.target_host, self.target_port),
            "cid": self.label,
            "qos": 1
        }
        if self.auth:
            template = template + MOSQ_BRIDGE_CFG_TEMPLATE_PSK
            aa = self.auth.split(":")
            inputs["psk_id"] = aa[0]
            inputs["psk_key"] = aa[1]

        return template % inputs

    def __init__(self, target_host, target_port, label=None, auth=None):
        self.target_host = target_host
        self.target_port = target_port
        self.label = label
        self.auth = auth
        self.log = logging.getLogger(__name__ + "_" + label)

    def __enter__(self):
        conf = self._make_config()
        # Save it to a temporary file
        self._f = tempfile.NamedTemporaryFile(delete=False)
        self._f.write(conf)
        self._f.close()
        self.log.debug("Creating config file %s: <%s>", self._f.name, conf)

        # too important, even though _f.close() has finished :(
        time.sleep(1)
        args = ["mosquitto", "-c", self._f.name]
        self._mosq = subprocess.Popen(args)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.log.debug("Swatting mosquitto on exit")
        os.unlink(self._f.name)
        # Attempt to let messages still get out of the broker...
        time.sleep(2)
        self._mosq.terminate()
        self._mosq.wait()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    b = BridgingSender("localhost", 1883, "hohoho")
    # b = BridgingSender("localhost", 8883, "hohoho", "karlos:01230123")
    generator = beem.msgs.GaussianSize("karlos", 10, 100)
    b.run(generator, 1)

    # b = ThreadedBridgingSender("localhost", 1883, "hohoho", ratio=20)
    # generator = beem.msgs.GaussianSize
    # generator_args = ("karlos", 10, 100)
    # b.run(generator, generator_args, 1)
