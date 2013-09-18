#!/usr/bin/env python
# Fabric magic for running malaria on multiple hosts
# Karl Palsson, September, 2013, <karlp@remake.is>

import fabric.api as fab
import fabric.tasks
import fabric.contrib as fabc
from fabtools.vagrant import vagrant  # for CLI usage
import fabtools as fabt
fab.env.project = "malaria"


@fab.task
def deploy():
    fab.local("rm -rf dist")
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
        #fab.run("pip install -e %s" % path_to_tarball)
        # work around https://github.com/ronnix/fabtools/issues/157 by upgrading pip
        # and also work around require.python.pip using sudo!
        with fab.settings(sudo_user=fab.env.user):
            fabt.require.python.pip()
        fabt.python.install("%(malaria_home)s/%(project)s.tar.gz" % fab.env)

@fab.task
def cleanup():
    fab.run("rm -rf /tmp/malaria-tmp-*")

def everybody():
    # this is needed at least once, but should have been covered
    # by either vagrant bootstrap, or your cloud machine bootstrap
    # TODO - move vagrant bootstrap to a fab bootstrap target instead?
    #fab.sudo("apt-get update")
    fabt.require.deb.packages([
        "python-dev",
        "python-virtualenv"
    ])

@fab.task
@fab.parallel
def publish(target):
    everybody()

    deploy()
    with fabt.python.virtualenv("%(malaria_home)s/venv" % fab.env):
        fab.run("malaria publish -n 100 -P 10 -t -H %s" % target)
    cleanup()
