Running malaria in a swarm
==========================

malaria includes [fabric](http://docs.fabfile.org/) scripts to help automate
running the command line utilities on multiple hosts.  This has seen use with
both [vagrant](http://www.vagrantup.com/), and also Amazone EC2 instances

Notes:
* attack nodes are only tested on ubuntu 1204 machines at this point
* To use the vagrant setup, you need https://github.com/ronnix/fabtools/pull/177

Fabric doesn't/can't provide as much help on the command line as the python
scripts can, so here's a basic overview

Get malaria
===========
You should get a clone of malaria locally first.

    git clone https://github.com/remakeelectric/mqtt-malaria.git

To use fabric, you either need to install fabric and all the ec2 tools
yourself, or, make a python virtualenv and install malaria into it.  This
will install all the dependencies you need

```
virtualenv .env
. .env/bin/activate
pip install -e .
fab -l # list all available fab commands
fab -d beeup # get documentation on the beeup command
```


There are two main tools that can be used for watching an attack, 
malaria subscribe and malaria watch.

Use malaria to watch an attack (new hotness method)
==================================================
"malaria subscribe" is a useful tool, but it relies heavily on knowing what
pattern of traffic is being sent.

"malaria watch" on the other hand is much more passive, and suitable for just
leaving running.  It collects less stats, but probably ones more interesting
to a load tester, and with less configuration.  There's no fab support for
this yet, you ssh to the target and run it there.  Also, note that it's not
designed to run by itself.  It's used in conjunction with somthing like 
[vmstatplot](https://github.com/remakeelectric/VmstatPlot) to collect
statistics.

Deploy malaria to the target as usual and then start monitoring...

```
fab -H target.machine cleanup deploy
ssh target.machine
cd /tmp
mkdir /tmp/mqttfs
. $(cat malaria-tmp-homedir)/venv/bin/activate
(venv)karlp@target.machine:/tmp/malaria-tmp-XXXX$ malaria watch -t "#" -d /tmp/mqttfs
```

This creates a pseudo file system with some statics files in it, this is a
lot like the way linux's /proc file system works.

Sidebar - Using vmstatplot
=========================
vmstatplot is a graphing wrapper around "vmstat" that includes the contents of
some files, like the virtual files in the mqttfs directory we made above.
You should mostly read the README it provides, but basically, you start it,
and then run collect every now and again to make a graph.


Use malaria to watch an attack (old busted method)
==============================
"malaria subscribe" is one command line utility for watching the
messages published and collecting stats.  This takes a lot of cpu, but it
collects stats on flight time, duples, missing and so on.  This also needs
to know the exact parameters of the attack, so it knows what to expect.

I've since found this to be not super useful, it's more useful for
constrained testing on a local machine, rather than long term load testing.

*note* you may wish to run this locally, connecting to the remote target
like so *UPDATE THIS with more real world experience*

    ./malaria -H attack_target -x -y -z

This may be a reduced cpu load on the target, but will use network bandwidth instead

### Install malaria software on the target

    fab -H attack_target deploy

### Run the listener

Be prepared to enter a malaria subscribe command appropriate to your warhead
(See below) and number of attack nodes.  
Any commands you enter are executed on the remote host, inside a virtualenv
created for the observer. Use Ctrl-C to exit the command prompt

    fab -H attack_target observe 


### Remove malaria from the target

    fab -H attack_target cleanup

Setup AWS Attack Nodes
==========================
"boto" is the python library for interacting with ec2.

Make a ~/.boto file like so
```
[Credentials]
aws_access_key_id = GET_THESE_FROM_
aws_secret_access_key = _YOUR_AWS_CONSOLE_WEBPAGE
```
If you don't know the secret part, you'll need to make a new credential, but
that's something for you to work out!

Setup malaria on all attack nodes
```
# Turn on 5 bees in eu-west-1 (see fab -d beeup for other options)
fab beeup:5,key_name=blahblahblah
# run apt-get update on all of them
fab -i path_to_blahblahblah.pem mstate aptup
# Install all dependencies in parallel
fab -i path_to_blahblahblah.pem mstate everybody:True
# deploy malaria code itself (serial unfortunately, help wanted!)
fab -i path_to_blahblahblah.pem mstate deploy
# If using bridging and tls-psk, generate/split your keyfile amongst all attack nodes
malaria keygen -n 20000 > malaria.pskfile
fab -i path_to_blahblahblah.pem mstate share_key:malaria.pskfile
```


Use malaria to attack (AWS Nodes)
=================================

Choose a warhead.  Warheads are basically command scripts that are executed on
each of your nodes.  Normally, the warhead runs one of the general malaria
publish commands that you can also run from your local clone of the malaria
repository.  An example warhead is
```
# 100 clients at 1 mps, 500 bytes, for 1000 mesages
malaria publish -p 8883 -b --psk_file /tmp/malaria-tmp-keyfile -P 100 -n 1000 -T 1 -s 500 -t -H %(malaria_target)s
```

This runs 100 clients on _each_ of your attack nodes.  So with 10 worker bees,
this will make 1000 clients, each publishing at 1 message per second.

With a warhead chosen, run the attack...
```
fab -i path_to_blahblahblah.pem mstate attack:target.machine.name,warhead=path_to_warhead_file
```

This may take a long time, of course.  If you'd like to abort a test, pressing
ctrl-c on the fabric script will often leave things running on the far side.
The fab script includes a target that will abort any running malaria/mosquitto
instances on the worker bees.

```
fab -i path_to_blahblahblah.pem mstate abort
```

That's it for attacking.  To shut down your AWS bees, (terminate them)
```
fab -i path_to_blahblahblah.pem mstate down
```

Technical notes
===============
The "mstate" target works by saving all the information about created worker
bees in the ~/.malaria file.  fab down removes this.  This is why you don't
need to specify all the hosts each time.

Use malaria to attack (Vagrant nodes)
====================================
Below are a set of commands suitable for use with either Vagrant boxes
or with "real" hosts created externally.

Depending on your ssh key/password options, you may need extra options
to "fab"

### Optionally, Create & setup two vagrant virtual machines to be attack nodes

    vagrant up

### Install malaria software on each node and prepare to attack

    fab vagrant up
    or
    fab -H attack-node1.example.org,attack-node2.example.org,... up

### Instruct all nodes from the "up" phase to attack a target with a warhead.
You can run multiple attacks after "up"

    fab -i /home/karlp/.vagrant.d/insecure_private_key mstate attack:mqtt-target.example.org,warhead=warheads/complex_10x10-bursty-double_publish.warhead
    fab attack:mqtt-target.example.org

### Stop and remove all malaria code from attack nodes

    fab -i /home/karlp/.vagrant.d/insecure_private_key down
    fab down

### Optionally, Destroy and turn off the vagrant virtual machines created

    vagrant destroy

