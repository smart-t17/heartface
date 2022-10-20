#!/bin/sh
#
# Add current user's ssh public key to the authorized keys
#  of root on the target system.
#

cat $HOME/.ssh/id_rsa.pub | ssh root@$1 -C "mkdir -p /root/.ssh && cat >> /root/.ssh/authorized_keys2 && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys2"