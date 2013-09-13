A set of tools to help with testing the scalability and load behaviour
of MQTT environments.

Contributions welcome!

Requires mosquitto python library 1.x or greater. (1.2 will give arguably
better performance as the "max messages in flight" parameter can be tweaked)

Similar Work
============
* http://affolter-engineering.ch/mqtt-randompub/ Appeared as I was finishing this.
* https://github.com/chirino/mqtt-benchmark

```
usage: load_publisher.py [-h] [-c CLIENTID] [-H HOST] [-p PORT] [-q {0,1,2}]
                         [-n MSG_COUNT] [-s MSG_SIZE] [-P PROCESSES]

Publish a stream of messages and capture statistics on their timing

optional arguments:
  -h, --help            show this help message and exit
  -c CLIENTID, --clientid CLIENTID
                        Set the client id of the publisher, can be useful for
                        acls Default has pid information appended (default:
                        beem.loadr-4979)
  -H HOST, --host HOST  MQTT host to connect to (default: localhost)
  -p PORT, --port PORT  Port for remote MQTT host (default: 1883)
  -q {0,1,2}, --qos {0,1,2}
                        set the mqtt qos for messages published (default: 1)
  -n MSG_COUNT, --msg_count MSG_COUNT
                        How many messages to send (default: 10)
  -s MSG_SIZE, --msg_size MSG_SIZE
                        Size of messages to send. This will be gaussian at (x,
                        x/20) unless the make_payload method is overridden
                        (default: 100)
  -P PROCESSES, --processes PROCESSES
                        How many separate processes to spin up
                        (multiprocessing) (default: 1)
```

To fire up 8 processes each sending 10000 messages of ~100 bytes each
```
  python load_publisher.py -P 8 -n 10000 -H mqtt.example.org -s 100
```

Example output
```
$ python load_publisher.py -P 4 -n 100 
Still waiting for results from 4 process(es)
INFO:beem.load:beem.loadr-5149-5153:Finished publish 100 msgs of 100 bytes at qos 1
INFO:beem.load:beem.loadr-5149-5153:Waiting for 79 messages to be confirmed still...
INFO:beem.load:beem.loadr-5149-5152:Finished publish 100 msgs of 100 bytes at qos 1
INFO:beem.load:beem.loadr-5149-5152:Waiting for 100 messages to be confirmed still...
INFO:beem.load:beem.loadr-5149-5150:Finished publish 100 msgs of 100 bytes at qos 1
INFO:beem.load:beem.loadr-5149-5150:Waiting for 97 messages to be confirmed still...
INFO:beem.load:beem.loadr-5149-5151:Finished publish 100 msgs of 100 bytes at qos 1
INFO:beem.load:beem.loadr-5149-5151:Waiting for 68 messages to be confirmed still...
Still waiting for results from 4 process(es)
Still waiting for results from 4 process(es)
Still waiting for results from 4 process(es)
Still waiting for results from 4 process(es)
Clientid: beem.loadr-5149-5150
Message succes rate: 100.00% (100/100 messages)
Message timing mean   985.87 ms
Message timing stddev 172.52 ms
Message timing min    7.00 ms
Message timing max    1033.22 ms
Clientid: beem.loadr-5149-5151
Message succes rate: 100.00% (100/100 messages)
Message timing mean   694.60 ms
Message timing stddev 468.93 ms
Message timing min    6.39 ms
Message timing max    1034.09 ms
Clientid: beem.loadr-5149-5152
Message succes rate: 100.00% (100/100 messages)
Message timing mean   1013.39 ms
Message timing stddev 11.32 ms
Message timing min    992.73 ms
Message timing max    1029.75 ms
Clientid: beem.loadr-5149-5153
Message succes rate: 100.00% (100/100 messages)
Message timing mean   47.12 ms
Message timing stddev 22.61 ms
Message timing min    8.61 ms
Message timing max    74.30 ms
Clientid: Aggregate stats (simple avg) for 4 processes
Message succes rate: 100.00% (400/400 messages)
Message timing mean   685.24 ms
Message timing stddev 168.85 ms
Message timing min    253.68 ms
Message timing max    792.84 ms
```
