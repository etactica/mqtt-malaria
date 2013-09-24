Running malaria in a swarm
==========================

malaria includes [fabric](http://docs.fabfile.org/) scripts to help automate
running the command line utilities on multiple hosts.  At present this is
mostly setup with [vagrant](http://www.vagrantup.com/), but the goal is to
use Amazon EC2 instances eventually. (more like Bees with Machine Guns)

Notes:
* attack nodes are only tested on ubuntu 1204 machines at this point
* To use the vagrant setup, you need https://github.com/ronnix/fabtools/pull/177

Fabric doesn't/can't provide as much help on the command line as the python
scripts can, so here's a basic overview

Get malaria
===========
You should get a clone of malaria locally first.

    git clone https://github.com/remakeelectric/mqtt-malaria.git

*TODO* Tidy this up...
Optionally make a virtualenv, or otherwise get fab
```
virtualenv .env
. .env/bin/activate
pip install -e .
???
```

Use malaria to watch an attack
==============================
"malaria subscribe" the command line utility is used for watching the
messages published and collecting stats.  Eventually, this should also
collect stats on CPU, MEM and IO load on the target server...

To set up an attack observer it _must_ know parameters about the attack!
This is so it knows what and how many messages to expect and when to finish
and calculate statistics.

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


Use malaria to attack
=====================
*TODO* This will need lots of expansion when I get AWS properly running.
Below are a set of commands suitable for use with either Vagrant boxes
or with "real" hosts created externally.

Depending on your ssh key/password options, you may need extra options
to "fab"

### Optionally, Create & setup two vagrant virtual machines to be attack nodes

    vagrant up

### Install malaria software on each node and prepare to attack

    fab vagrant up
    fab -H attack-node1.example.org,attack-node2.example.org,... up

### Instruct all nodes from the "up" phase to attack a target with a warhead.
You can run multiple attacks after "up"

    fab -a -i /home/karlp/.vagrant.d/insecure_private_key attack:mqtt-target.example.org,warhead=warheads/complex_10x10-bursty-double_publish.warhead
    fab attack:mqtt-target.example.org

### Stop and remove all malaria code from attack nodes

    fab -a -i /home/karlp/.vagrant.d/insecure_private_key down
    fab down

### Optionally, Destroy and turn off the vagrant virtual machines created

    vagrant destroy

