#!/bin/sh

docker build -t nginx-upload .

cp /usr/sbin/nginx /usr/sbin/nginx.orig
docker run -t -v /usr/sbin:/dest nginx-upload bash -c 'cp /usr/sbin/nginx /usr'
