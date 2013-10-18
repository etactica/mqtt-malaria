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
import socket
import subprocess
import tempfile
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

    def get_free_listen_port(self):
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

    def make_config(self, target_host, target_port):
        """
        Make an appropriate mosquitto config snippet out of
        our params and saved state
        """
        template = MOSQ_BRIDGE_CFG_TEMPLATE
        inputs = {
            "listen_port": self.lport,
            "malaria_target": "%s:%d" % (target_host, target_port),
            "cid": self.cid,
            "qos": 1
        }
        if self.auth:
            template = template + MOSQ_BRIDGE_CFG_TEMPLATE_PSK
            aa = self.auth.split(":")
            inputs["psk_id"] = aa[0]
            inputs["psk_key"] = aa[1]

        return template % inputs

    def __init__(self, target_host, target_port, cid, auth=None):
        self.cid = cid
        self.auth = auth
        self.log = logging.getLogger(__name__ + ":" + cid)
        self.lport = self.get_free_listen_port()

        conf = self.make_config(target_host, target_port)
        # Save it to a temporary file
        self.mos_cfg = tempfile.NamedTemporaryFile()
        self.log.debug("Creating temporary bridge config in %s",
                       self.mos_cfg.name)
        self.mos_cfg.write(conf)
        self.mos_cfg.flush()
        time.sleep(1)
        args = ["mosquitto", "-c", self.mos_cfg.name]
        self.mos = subprocess.Popen(args)
        # wait for start, or the tracking sender will fail to connect...
        time.sleep(3)
        # TODO - should we start our own listener here and wait for status on
        # the bridge? Otherwise we don't detect failures of the bridge
        # to come up?
        self.log.info("Created bridge and child mosquitto, cid: %s, auth: %s"
                      % (self.cid, self.auth))

    def run(self, generator, qos=1):
        # Make this ts to send to our bridge...
        self.ts = beem.load.TrackingSender("localhost", self.lport, self.cid)
        self.ts.run(generator, qos)
        # This leaves enough time for the sender to disconnect before we
        # just kill mosquitto
        time.sleep(1)
        self.log.debug("killing mosquitto")
        self.mos.terminate()
        self.mos.wait()

    def stats(self):
        return self.ts.stats()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    #b = BridgingSender("localhost", 1883, "hohoho")
    b = BridgingSender("localhost", 8883, "hohoho", "karlos:01230123")
    generator = beem.msgs.GaussianSize("karlos", 10, 100)
    b.run(generator, 1)
