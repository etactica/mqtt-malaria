#!/usr/bin/env python
# Fabric magic for running malaria on multiple hosts
# Karl Palsson, September, 2013, <karlp@remake.is>

import json
import os
import fabric.api as fab
import fabric.tasks
import fabric.contrib as fabc
from fabtools.vagrant import vagrant  # for CLI usage
import fabtools as fabt
fab.env.project = "malaria"

STATE_FILE = os.path.expanduser("~/.malaria")

def _load_state():
    if not os.path.isfile(STATE_FILE):
        return None

    return json.load(open(STATE_FILE, 'r'))

def _save_state(state):
    json.dump(state, open(STATE_FILE, 'w'),
              sort_keys=True, indent=4)


@fab.task
@fab.parallel
def deploy():
    fab.local("rm -rf dist")
    # FIXME - this bit can't be parallel actually....
    # come up with some other way to check for this...
    fab.local("python setup.py sdist")
    # figure out the release name and version
    dist = fab.local('python setup.py --fullname', capture=True).strip()

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
    fab.run("rm -rf /tmp/malaria-tmp-*")
    fab.local("rm -f ~/.malaria")

def everybody():
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

@fab.task
@fab.parallel
def up():
    state = {"hosts": fab.env.hosts}
    everybody()
    deploy()
    _save_state(state)


@fab.task
@fab.parallel
def _attack(target):
    fab.env.malaria_home = fab.run("cat /tmp/malaria-tmp-homedir")
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        fab.run("malaria publish -n 10 -P 10 -t -T 1 -H %s" % target)

@fab.task
def attack(target):
    state = _load_state()
    if not state:
        fab.abort("No state file found with active servers? %s" % STATE_FILE)
    fab.env.hosts = state["hosts"]
    # Indirection necessary to fiddle with the host list like this.
    fab.execute(_attack, target)


@fab.task
def down():
    state = _load_state()
    if not state:
        fab.abort("No state file found with active servers? %s" % STATE_FILE)
    fab.env.hosts = state["hosts"]
    fab.execute(cleanup)


@fab.task
@fab.parallel
def publish(target, *args):
    everybody()

    deploy()
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        #fab.run("malaria publish -n 10 -P 10 -t -T 1 -H %s" % target)
        fab.run("malaria publish -H %s %s" % (target, ' '.join(args)))
    cleanup()

@fab.task
@fab.serial
def listen(target, *args):
    everybody()

    deploy()
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        #fab.run("malaria subscribe -n 10 -N 20 -H %s" % target)
        fab.run("malaria subscribe -H %s %s" % (target, ' '.join(args)))
    cleanup()
