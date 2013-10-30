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
Basic helper routines that might be needed in multiple places.
Also, just a place holder for the package.
"""


def print_publish_stats(stats):
    """
    pretty print a stats object that held publisher details
    """
    if not stats.get("clientid", None):
        raise ValueError("Can't print stats on a non stats object?!", stats)
    print("Clientid: %s" % stats["clientid"])
    print("Message succes rate: %.2f%% (%d/%d messages)"
          % (100 * stats["rate_ok"], stats["count_ok"], stats["count_total"]))
    print("Message timing mean   %.2f ms" % stats["time_mean"])
    print("Message timing stddev %.2f ms" % stats["time_stddev"])
    print("Message timing min    %.2f ms" % stats["time_min"])
    print("Message timing max    %.2f ms" % stats["time_max"])
    print("Messages per second   %.2f" % stats["msgs_per_sec"])
    print("Total time            %.2f secs" % stats["time_total"])


def aggregate_publish_stats(stats_set):
    """
    For a set of per process _publish_ stats, make some basic aggregated stats
    timings are a simple mean of the input timings. ie the aggregate
    "minimum" is the average of the minimum of each process, not the
    absolute minimum of any process.
    Likewise, aggregate "stddev" is a simple mean of the stddev from each
    process, not an entire population stddev.
    """
    def naive_average(the_set):
        return sum(the_set) / len(the_set)
    count_ok = sum([x["count_ok"] for x in stats_set])
    count_total = sum([x["count_total"] for x in stats_set])
    cid = "Aggregate stats (simple avg) for %d processes" % len(stats_set)
    avg_msgs_per_sec = naive_average([x["msgs_per_sec"] for x in stats_set])
    return {
        "clientid": cid,
        "count_ok": count_ok,
        "count_total": count_total,
        "rate_ok": count_ok / count_total,
        "time_min": naive_average([x["time_min"] for x in stats_set]),
        "time_max": naive_average([x["time_max"] for x in stats_set]),
        "time_mean": naive_average([x["time_mean"] for x in stats_set]),
        "time_stddev": naive_average([x["time_stddev"] for x in stats_set]),
        "msgs_per_sec": avg_msgs_per_sec * len(stats_set)
    }
