#!/usr/bin/env python

import beem.load

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
    ts.stats()
