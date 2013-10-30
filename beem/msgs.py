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
Message generator implementations
"""
import string
import random
import time


def GaussianSize(cid, sequence_size, target_size):
    """
    Message generator creating gaussian distributed message sizes
    centered around target_size with a deviance of target_size / 20
    """
    num = 1
    while num <= sequence_size:
        topic = "mqtt-malaria/%s/data/%d/%d" % (cid, num, sequence_size)
        real_size = int(random.gauss(target_size, target_size / 20))
        payload = ''.join(random.choice(string.hexdigits) for _ in range(real_size))
        yield (num, topic, payload)
        num = num + 1


def TimeTracking(generator):
    """
    Wrap an existing generator by prepending time tracking information
    to the start of the payload.
    """
    for a, b, c in generator:
        newpayload = "{:f},{:s}".format(time.time(), c)
        yield (a, b, newpayload)


def RateLimited(generator, msgs_per_sec):
    """
    Wrap an existing generator in a rate limit.
    This will probably behave somewhat poorly at high rates per sec, as it
    simply uses time.sleep(1/msg_rate)
    """
    for x in generator:
        yield x
        time.sleep(1 / msgs_per_sec)


def JitteryRateLimited(generator, msgs_per_sec, jitter=0.1):
    """
    Wrap an existing generator in a (jittery) rate limit.
    This will probably behave somewhat poorly at high rates per sec, as it
    simply uses time.sleep(1/msg_rate)
    """
    for x in generator:
        yield x
        desired = 1 / msgs_per_sec
        extra = random.uniform(-1 * jitter * desired, 1 * jitter * desired)
        time.sleep(desired + extra)


def createGenerator(label, options, index=None):
    """
    Handle creating an appropriate message generator based on a set of options
    index, if provided, will be appended to label
    """
    cid = label
    if index:
        cid += "_" + str(index)
    msg_gen = GaussianSize(cid, options.msg_count, options.msg_size)
    if options.timing:
        msg_gen = TimeTracking(msg_gen)
    if options.msgs_per_second > 0:
        if options.jitter > 0:
            msg_gen = JitteryRateLimited(msg_gen,
                                         options.msgs_per_second,
                                         options.jitter)
        else:
            msg_gen = RateLimited(msg_gen, options.msgs_per_second)
    return msg_gen
