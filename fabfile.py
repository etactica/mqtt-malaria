#!/usr/bin/env python
# Fabric malaria_split_keys for running malaria on multiple hosts
# Karl Palsson, September, 2013, <karlp@remake.is>

import json
import os
import random
import tempfile
import time

import fabric.api as fab
from fabtools.vagrant import vagrant  # for CLI usage
import fabtools as fabt
import boto
import boto.ec2

import beem.cmds.keygen as keygen

fab.env.project = "malaria"


STATE_FILE = os.path.expanduser("~/.malaria")


def _load_state():
    if not os.path.isfile(STATE_FILE):
        return None

    return json.load(open(STATE_FILE, 'r'))


def _save_state(state):
    json.dump(state, open(STATE_FILE, 'w'),
              sort_keys=True, indent=4)


@fab.runs_once
def _pack():
    fab.local("rm -rf dist")
    # FIXME - this bit can't be parallel actually....
    # come up with some other way to check for this...
    fab.local("python setup.py sdist")
    # figure out the release name and version
    dist = fab.local('python setup.py --fullname', capture=True).strip()
    return dist


@fab.task
def deploy(install_mosquitto=False):
    """
    Install malaria on a given host.

    malaria will be installed to a virtual env in a temporary directory, and
    /tmp/malaria-tmp-homedir will contain the full path for subsequent
    operations on this host.

    if deploy:True, then install mosquitto and mosquitto-clients as well,
    this is necessary if you are hoping to use bridge tests, but is not done
    automatically as you may wish to use a specific version of mosquitto 
    """
    everybody(install_mosquitto)

    # This has to be serial, as it runs locally
    dist = _pack()

    # Make a very temporary "home" remotely
    fab.env.malaria_home = fab.run("mktemp -d -t malaria-tmp-XXXXXX")

    # upload the source tarball to the temporary folder on the server
    fab.put('dist/%s.tar.gz' % dist,
            '%(malaria_home)s/%(project)s.tar.gz' % fab.env)

    # Now make sure there's a venv and install ourselves into it.
    venvpath = "%(malaria_home)s/venv" % fab.env
    fabt.require.python.virtualenv(venvpath)
    with fabt.python.virtualenv(venvpath):
        # work around https://github.com/ronnix/fabtools/issues/157 by upgrading pip
        # and also work around require.python.pip using sudo!
        with fab.settings(sudo_user=fab.env.user):
            fabt.require.python.pip()
        fabt.python.install("%(malaria_home)s/%(project)s.tar.gz" % fab.env)
    fabt.require.files.file("/tmp/malaria-tmp-homedir", contents=fab.env.malaria_home)


@fab.task
@fab.parallel
def cleanup():
    """
    Remove all malaria code that was installed on a target

    TODO - should this attempt to stop running processes if any?
    """
    fab.run("rm -rf /tmp/malaria-tmp-*")


@fab.task
def beeup(count, region="eu-west-1", ami="ami-c27b6fb6", group="quick-start-1", key_name="karl-malaria-bees-2013-oct-15"):
    """
    Fire up X ec2 instances,
    no checking against how many you already have!
    Adds these to the .malaria state file, and saves their instance ids
    so we can kill them later.

    args:
        count (required) number of bees to spin up
        region (optional) defaults to "eu-west-1"
        ami (optional) defaults to ami-c27b6fb6 (Ubu 1204lts 32bit in eu-west1)
                ami-a53264cc is the same us-east-1
        group (optional) defaults to "quick-start-1"
            needs to be a security group that allows ssh in!
        key_name (optional) defaults to karl-malaria-bees-2013-oct-15
            you need to have precreated this in your AWS console and have the private key available
    """
    count = int(count)
    state = _load_state()
    if state:
        fab.puts("already have hosts available: %s, will add %d more!" %
                 (state["hosts"], count))
    else:
        state = {"hosts": [], "aws_iids": []}

    ec2_connection = boto.ec2.connect_to_region(region)
    instance_type = "t1.micro"

    zones = ec2_connection.get_all_zones()
    zone = random.choice(zones).name

    reservation = ec2_connection.run_instances(
        image_id=ami,
        min_count=count,
        max_count=count,
        key_name=key_name,
        security_groups=[group],
        instance_type=instance_type,
        placement=zone
        )
    print("Reservation is ", reservation)
    fab.puts("Waiting for Amazon to breed bees")
    instances = []
    for i in reservation.instances:
        i.update()
        while i.state != "running":
            print(".")
            time.sleep(2)
            i.update()
        instances.append(i)
        fab.puts("Bee %s ready for action!" % i.id)
    # Tag these so that humans can understand these better in AWS console
    # (We just use a state file to spinup/spindown)
    ec2_connection.create_tags([i.id for i in instances], {"malaria": "bee"})
    #state["aws_zone"] = no-one cares
    state["aws_iids"].extend([i.id for i in instances])
    for i in instances:
        hoststring = "%s@%s" % ("ubuntu", i.public_dns_name)
        state["hosts"].append(hoststring)
        fab.puts("Adding %s to our list of workers" % hoststring)
    _save_state(state)


def beedown(iids):
    """Turn off all our bees"""
    zone = "eu-west-1"
    ec2_connection = boto.ec2.connect_to_region(zone)
    tids = ec2_connection.terminate_instances(instance_ids=iids)
    fab.puts("terminated ids: %s" % tids)


@fab.task
@fab.parallel
def aptup():
    fab.sudo("apt-get update")


@fab.task
@fab.parallel
def everybody(install_mosquitto=False):
    # this is needed at least once, but should have been covered
    # by either vagrant bootstrap, or your cloud machine bootstrap
    # TODO - move vagrant bootstrap to a fab bootstrap target instead?
    #fab.sudo("apt-get update")
    family = fabt.system.distrib_family()
    if family == "debian":
        fabt.require.deb.packages([
            "python-dev",
            "python-virtualenv"
        ])
    if family == "redhat":
        fabt.require.rpm.packages([
            "python-devel",
            "python-virtualenv"
        ])

    if install_mosquitto:
        # FIXME - this only works for ubuntu....
        fab.puts("Installing mosquitto from ppa")
        fabt.require.deb.packages(["python-software-properties"])
        fabt.require.deb.ppa("ppa:mosquitto-dev/mosquitto-ppa")
        fabt.require.deb.packages(["mosquitto", "mosquitto-clients"])


@fab.task
def up():
    """
    Prepare a set of hosts to be malaria attack nodes.

    The set of machines are saved in ~/.malaria for to help with repeated
    attacks and for cleanup.
    """
    state = {"hosts": fab.env.hosts}
    deploy()
    _save_state(state)


@fab.task
def mstate():
    """
    Set fabric hosts from ~/.malaria

    Use this to help you run tasks on machines already configured.
    $ fab beeup:3
    $ fab mstate deploy
    or
    $ fab vagrant up XXXX Tidy up and make this more consistent!!!
    $ fab mstate attack:target.machine

    """
    state = _load_state()
    fab.env.hosts = state["hosts"]


@fab.task
@fab.parallel
def attack(target, warhead=None):
    """
    Launch an attack against "target" with all nodes from "up"

    "warhead" is a file of attack commands that will be run inside the
    malaria virtual environment on the attacking node.  See examples in
    the warheads directory.
    """
    fab.env.malaria_home = fab.run("cat /tmp/malaria-tmp-homedir")
    fab.env.malaria_target = target
    cmd = []

    if warhead:
        with open(warhead, "r") as f:
            cmds = [x for x in f if x.strip() and x[0] not in "#;"]
    else:
        cmds = ["malaria publish -n 10 -P 10 -t -T 1 -H %(malaria_target)s"]

    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        for cmd in cmds:
            fab.run(cmd % fab.env)


@fab.task
@fab.parallel
def abort():
    """
    Attempt to kill all processes that might be related to a malaria attack
    
    """
    with fab.settings(warn_only=True):
        fab.run("kill $(pgrep malaria)", )
        # TODO - should only be done when bridging?
        fab.run("kill $(pgrep mosquitto)")

@fab.task
def down():
    """
    Clear our memory and cleanup all malaria code on all attack nodes

    TODO - this should turn off AWS-EC2 instances if we turned them on!
    """
    state = _load_state()
    if not state:
        fab.abort("No state file found with active servers? %s" % STATE_FILE)
    if state["aws_iids"]:
        beedown(state["aws_iids"])
    else:
        fab.puts("Cleaning up regular hosts (that we leave running)")
        fab.env.hosts = state["hosts"]
        fab.execute(cleanup)
    fab.local("rm -f ~/.malaria")


@fab.task
def observe():
    """
    Watch the outcome of the attack

    Run this to setup the stats collector on the target
    """
    fab.env.malaria_home = fab.run("cat /tmp/malaria-tmp-homedir")

    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        # Default is for the two vagrant machines, default attack command
        while True:
            cmd = fab.prompt(
                "Enter command to run in malaria virtual env $",
                default="malaria subscribe -n 10 -N 20")
            if cmd.strip():
                fab.run(cmd % fab.env)
            else:
                fab.puts("Ok, done done!")
                break


@fab.task
@fab.parallel
def publish(target, *args):
    deploy()
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        #fab.run("malaria publish -n 10 -P 10 -t -T 1 -H %s" % target)
        fab.run("malaria publish -H %s %s" % (target, ' '.join(args)))
    cleanup()


@fab.task
@fab.serial
def listen(target, *args):
    deploy()
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        #fab.run("malaria subscribe -n 10 -N 20 -H %s" % target)
        fab.run("malaria subscribe -H %s %s" % (target, ' '.join(args)))
    cleanup()


@fab.task
@fab.runs_once
def _presplit(keyfile):
    """magically split the file into ram and tack it into the fab.env...."""
    with open(keyfile, "r") as f:
        inputs = f.readlines()
    count = len(fab.env.hosts)
    fab.env.malaria_split_keys = dict(zip(fab.env.hosts,
                                          keygen.chunks(inputs, count)))


@fab.task
@fab.parallel
def share_key(keyfile, fname="/tmp/malaria-tmp-keyfile"):
    """
    Take a key file and split it amongst all the given hosts,
    installs to /tmp/malaria-tmp-keyfile.
    TODO: should save it into the %(malaria_home) directory?
    """
    fab.execute(_presplit, keyfile)
    fab.puts("Distributing keys to host: %s" % fab.env.host_string)
    our_keys = fab.env.malaria_split_keys[fab.env.host_string]
    with tempfile.NamedTemporaryFile() as f:
        [f.write(l) for l in our_keys]
        f.flush()
        fab.put(f.name, fname)
