#!/usr/bin/env python

import argparse
import logging
import os
import beem.load

logging.basicConfig(level=logging.INFO)

def custom_make_topic(seq):
    return "karlosssssss_%d" % seq

def custom_make_payload(seq, size):
    return "Message %d was meant to be %d bytes long hehe" % (seq, size)

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        Publish a stream of messages and capture statistics on their timing
        """)

    parser.add_argument(
        "-c", "--clientid", default="beem.loadr-%d" % os.getpid(),
        help="Set the client id of the publisher, can be useful for acls")
    parser.add_argument(
        "-H", "--host", default="localhost",
        help="MQTT host to connect to")
    parser.add_argument(
        "-p", "--port", type=int, default=1883,
        help="Port for remote MQTT host")
    parser.add_argument(
        "-q", "--qos", type=int, choices=[0, 1, 2],
        help="set the mqtt qos for messages published", default=1)
    parser.add_argument(
        "-n", "--msg_count", type=int, default=10,
        help="How many messages to send")
    parser.add_argument(
        "-s", "--msg_size", type=int, default=100,
        help="""Size of messages to send. This will be gaussian at (x, x/20)
unless the make_payload method is overridden""")


    options = parser.parse_args()

    ts = beem.load.TrackingSender(options.host, options.port, options.clientid)
    # Provide a custom topic generator
    #ts.make_topic = custom_make_topic
    # Or a custom payload generator
    #ts.make_payload = custom_make_payload
    ts.run(options.msg_count, options.msg_size, options.qos)
    stats = ts.stats()
    print("Message succes rate: %.2f%% (%d/%d messages)"
        % (100 * stats["rate_ok"], stats["count_ok"], stats["count_total"]))
    print("Message timing mean   %.2f ms" % stats["time_mean"])
    print("Message timing stddev %.2f ms" % stats["time_stddev"])
    print("Message timing min    %.2f ms" % stats["time_min"])
    print("Message timing max    %.2f ms" % stats["time_max"])


if __name__ == "__main__":
    main()
