#!/bin/sh
#
# Install pre-requsits for Ansible provisioning
#
# (Note: these are available on Linode/DO base debian images, so
#  no need to run it there.)
#

apt-get update && apt-get -y --no-install-recommends install openssh-server python-minimal python2.7
