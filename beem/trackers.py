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
classes to help with tracking message status
"""
import time


class SentMessage():
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
            return ("MSG(%d) OK, flight time: %f seconds"
                    % (self.mid, self.time_flight()))
        else:
            return ("MSG(%d) INCOMPLETE in flight for %f seconds so far"
                    % (self.mid, time.time() - self.time_created))


class ObservedMessage():
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
        payload_segs = msg.payload.split(",")
        self.time_created = time.mktime(time.localtime(float(payload_segs[0])))
        self.time_received = time.time()

    def time_flight(self):
        return self.time_received - self.time_created

    def __repr__(self):
        return ("MSG(%s:%d) OK, flight time: %f ms (c:%f, r:%f)"
                % (self.cid, self.mid, self.time_flight() * 1000,
                   self.time_created, self.time_received))

    def __eq__(self, y):
        return self.__key() == y.__key()

    def __hash__(self):
        return hash(self.__key())
