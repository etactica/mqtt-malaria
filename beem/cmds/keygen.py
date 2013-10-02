#!/usr/bin/env python
#
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
#
# This file implements the "malaria keygen" command
"""
Creates key files, suitable for use with mosquitto servers with tls-psk
(or, maybe even with username/password or tls-srp....)
"""

import argparse
import random
import string


def add_args(subparsers):
    parser = subparsers.add_parser(
        "keygen",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__,
        help="Create a keyfile for use with mosquitto")

    parser.add_argument(
        "-t", "--template", default="malaria-tlspsk-%d",
        help="""Set the template for usernames, the %%d will be replaced
        with a sequential number""")
    parser.add_argument(
        "-n", "--count", type=int, default=10,
        help="How many user/key pairs to generate")
    parser.add_argument(
        "-f", "--file", default="-", type=argparse.FileType("w"),
        help="File to write the generated keys to")
    parser.add_argument(
        "-F", "--infile", default="-", type=argparse.FileType("r"),
        help="File to read keys from")
    parser.add_argument(
        "-s", "--split", action="store_true",
        help="""Instead of generating 'count' keys into 'file', split file
        into count pieces, named file.1,2,3,4....""")

    parser.set_defaults(handler=run)


def generate(options):
    with options.file as f:
        for i in range(options.count):
            user = options.template % (i + 1)
            key = ''.join(random.choice(string.hexdigits) for _ in range(40))
            f.write("%s:%s\n" % (user, key))


def chunks(l, n):
    """
    Yield n successive chunks from l.
    Source: http://stackoverflow.com/a/2130042
    """
    newn = int(len(l) / n)
    for i in xrange(0, n - 1):
        yield l[i * newn:i * newn + newn]
    yield l[n * newn - newn:]


def split(file_handle, count):
    basename = file_handle.name
    with file_handle as f:
        inputs = f.readlines()
    print("splitting %d inputs into %d pieces " % (len(inputs), count))

    for i, lines in enumerate(chunks(inputs, count)):
        with open("%s.chunked.%d" % (basename, (i + 1)), "w") as f:
            print("writing %d entries to %s" % (len(lines), f.name))
            [f.write(l) for l in lines]


def run(options):
    if options.split:
        split(options.infile, options.count)
    else:
        generate(options)
