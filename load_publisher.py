#!/usr/bin/env python

import logging
import beem.load

logging.basicConfig(level=logging.INFO)

def custom_make_topic(seq):
    return "karlosssssss_%d" % seq

def custom_make_payload(seq, size):
    return "Message %d was meant to be %d bytes long hehe" % (seq, size)

if __name__ == "__main__":
    ts = beem.load.TrackingSender("localhost", 1883, "karlos1")
    # Provide a custom topic generator
    #ts.make_topic = custom_make_topic
    # Or a custom payload generator
    #ts.make_payload = custom_make_payload
    ts.run(100, 50)
    stats = ts.stats()
    print("Message succes rate: %.2f%% (%d/%d messages)"
        % (100 * stats["rate_ok"], stats["count_ok"], stats["count_total"]))
    print("Message timing mean   %.2f ms" % stats["time_mean"])
    print("Message timing stddev %.2f ms" % stats["time_stddev"])
    print("Message timing min    %.2f ms" % stats["time_min"])
    print("Message timing max    %.2f ms" % stats["time_max"])
