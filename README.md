A set of tools to help with testing the scalability and load behaviour
of MQTT environments.

Contributions welcome!

Install
=======

Requires python2, paho-mqtt python library 1.1 or greater, and fusepy.

```
virtualenv .env
. .env/bin/activate
pip install .
```

The tools are in multiple layers:

* Python modules for message generation and sending/receiving
  (Documented as pydoc)
* command line tools for sending/receiving with stats on a single host
  (Documented here)
* fabric scripts for running those tools on multiple hosts
  (Documented in README-swarm.md)

malaria publish
===============
The publisher can mimic multiple separate clients, publishing messages of
a known size, or with time of flight tracking information, at a known rate,
or simply as fast as possible.

Note, for higher values of "processes" you _will_ need to modify ulimit
settings!

The messages themselves are provided by generators that can be easily
plugged in, see beem.msgs


```
usage: malaria publish [-h] [-c CLIENTID] [-H HOST] [-p PORT]
                            [-q {0,1,2}] [-n MSG_COUNT] [-s MSG_SIZE] [-t]
                            [-T MSGS_PER_SECOND] [-P PROCESSES]

Publish a stream of messages and capture statistics on their timing

optional arguments:
  -h, --help            show this help message and exit
  -c CLIENTID, --clientid CLIENTID
                        Set the client id of the publisher, can be useful for
                        acls Default has pid information appended (default:
                        beem.loadr-8015)
  -H HOST, --host HOST  MQTT host to connect to (default: localhost)
  -p PORT, --port PORT  Port for remote MQTT host (default: 1883)
  -q {0,1,2}, --qos {0,1,2}
                        set the mqtt qos for messages published (default: 1)
  -n MSG_COUNT, --msg_count MSG_COUNT
                        How many messages to send (default: 10)
  -s MSG_SIZE, --msg_size MSG_SIZE
                        Size of messages to send. This will be gaussian at (x,
                        x/20) (default: 100)
  -t, --timing          Message bodies will contain timing information instead
                        of random hex characters. This overrides the --msg-
                        size option, obviously (default: False)
  -T MSGS_PER_SECOND, --msgs_per_second MSGS_PER_SECOND
                        Each publisher should target sending this many msgs
                        per second, useful for simulating real devices.
                        (default: 0)
  -P PROCESSES, --processes PROCESSES
                        How many separate processes to spin up
                        (multiprocessing) (default: 1)
```

Examples
--------

To fire up 8 processes each sending 10000 messages of ~100 bytes each,
sending as fast as the code allows.
```
  malaria publish -P 8 -n 10000 -H mqtt.example.org -s 100
```

To fire up 500 processes, each sending 5 messages per second, each sending
1000 messages, with time in flight tracking information
```
  malaria publish -t -n 1000 -P 500 -T 5
```

Example output
```
$ ./malaria publish -t -n 100 -P 4
Still waiting for results from 4 process(es)
INFO:beem.load:beem.loadr-9850-1:Finished publish 100 msgs at qos 1
INFO:beem.load:beem.loadr-9850-1:Waiting for 100 messages to be confirmed still...
Still waiting for results from 4 process(es)
INFO:beem.load:beem.loadr-9850-0:Finished publish 100 msgs at qos 1
INFO:beem.load:beem.loadr-9850-0:Waiting for 100 messages to be confirmed still...
INFO:beem.load:beem.loadr-9850-2:Finished publish 100 msgs at qos 1
INFO:beem.load:beem.loadr-9850-2:Waiting for 100 messages to be confirmed still...
Still waiting for results from 4 process(es)
INFO:beem.load:beem.loadr-9850-3:Finished publish 100 msgs at qos 1
INFO:beem.load:beem.loadr-9850-3:Waiting for 100 messages to be confirmed still...
Still waiting for results from 4 process(es)
Still waiting for results from 4 process(es)
Still waiting for results from 4 process(es)
Clientid: beem.loadr-9850-0
Message succes rate: 100.00% (100/100 messages)
Message timing mean   298.03 ms
Message timing stddev 13.85 ms
Message timing min    267.18 ms
Message timing max    304.76 ms
Messages per second   49.78
Total time            2.01 secs
Clientid: beem.loadr-9850-1
Message succes rate: 100.00% (100/100 messages)
Message timing mean   915.68 ms
Message timing stddev 15.22 ms
Message timing min    883.67 ms
Message timing max    924.15 ms
Messages per second   49.81
Total time            2.01 secs
Clientid: beem.loadr-9850-2
Message succes rate: 100.00% (100/100 messages)
Message timing mean   95.74 ms
Message timing stddev 15.99 ms
Message timing min    65.17 ms
Message timing max    104.73 ms
Messages per second   49.77
Total time            2.01 secs
Clientid: beem.loadr-9850-3
Message succes rate: 100.00% (100/100 messages)
Message timing mean   731.22 ms
Message timing stddev 18.25 ms
Message timing min    711.27 ms
Message timing max    748.39 ms
Messages per second   49.77
Total time            2.01 secs
Clientid: Aggregate stats (simple avg) for 4 processes
Message succes rate: 100.00% (400/400 messages)
Message timing mean   510.17 ms
Message timing stddev 15.83 ms
Message timing min    481.82 ms
Message timing max    520.51 ms
Messages per second   49.78
Total time            3.35 secs
```

malaria subscribe
==================
The subscriber side can listen to a broker and print out stats as messages 
are received.  It needs to be told how many messages and how many virtual
clients it should expect, and at least at present, requires the publisher to
be operating in "time of flight tracking" mode. (Instrumented payloads)

This works in single threaded mode (at present) modelling the use case of a
central data processor.  It aborts if it ever detects messages being dropped.

```
usage: malaria subscribe [-h] [-c CLIENTID] [-H HOST] [-p PORT]
                             [-q {0,1,2}] [-n MSG_COUNT] [-N CLIENT_COUNT]
                             [-t TOPIC]

Listen to a stream of messages and capture statistics on their timing

optional arguments:
  -h, --help            show this help message and exit
  -c CLIENTID, --clientid CLIENTID
                        Set the client id of the listner, can be useful for
                        acls Default has pid information appended. (default:
                        beem.listr-8391)
  -H HOST, --host HOST  MQTT host to connect to (default: localhost)
  -p PORT, --port PORT  Port for remote MQTT host (default: 1883)
  -q {0,1,2}, --qos {0,1,2}
                        set the mqtt qos for subscription (default: 1)
  -n MSG_COUNT, --msg_count MSG_COUNT
                        How many messages to expect (default: 10)
  -N CLIENT_COUNT, --client_count CLIENT_COUNT
                        How many clients to expect. See docs for examples of
                        how this works (default: 1)
  -t TOPIC, --topic TOPIC
                        Topic to subscribe to, will be sorted into clients by
                        the '+' symbol (default: mqtt-malaria/+/data/#)
```

Examples
--------
To monitor a publisher of 500 processes, 1000 msgs per process:
```
malaria subscribe -n 1000 -N 500
```

Example output:
```
$ ./malaria subscribe -n 1000 -N 500
INFO:beem.listen:beem.listr-8518:Listening for 500000 messages on topic mqtt-malaria/+/data/# (q1)
DEBUG:beem.listen:beem.listr-8518:Storing initial drop count: 62491
INFO:beem.listen:beem.listr-8518:Still waiting for 500000 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 500000 messages
----snip-----
INFO:beem.listen:beem.listr-8518:Still waiting for 16997 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 14550 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 12031 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 9608 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 7130 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 4626 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 2247 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 744 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 41 messages
INFO:beem.listen:beem.listr-8518:Still waiting for 0 messages
Clientid: beem.listr-8518
Total clients tracked: 500
Total messages: 500000
Total time: 203.94 secs
Messages per second: 2451 (0.407888 ms per message)
Messages duplicated: []
Flight time mean:   991.66 ms
Flight time stddev: 414.76 ms
Flight time min:    2.29 ms
Flight time max:    2076.39 ms

```


Similar Work
============
Bees with Machine guns was the original inspiration, and I still intend to
set this up such that the publisher components can be run as "bees"

Also
* http://affolter-engineering.ch/mqtt-randompub/ Appeared as I was finishing this.
* https://github.com/chirino/mqtt-benchmark
* http://www.ekito.fr/people/mqtt-benchmarks-rabbitmq-activemq/
* https://github.com/bluewindthings/mqtt-stress
* https://github.com/tuanhiep/mqtt-jmeter

