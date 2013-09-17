#!/bin/sh
apt-get -y install python-software-properties avahi-daemon
apt-add-repository ppa:mosquitto-dev/mosquitto-ppa

apt-get -y update
apt-get -y install mosquitto python-mosquitto mosquitto-clients

# You need this if you're setting up as a target, not a bee
#cp /etc/mosquitto/mosquitto.conf.example /etc/mosquitto/mosquitto.conf
#start mosquitto
