# Install
```
(env) $ pip install -r requirements/development.txt
```

Initial setup
=============

Before being able to run the project, you'll at least have to set up the database.
(Remember, local settings go into the local.py file.) You can use whatever
database you want, but it's best to use the same as production as different databases
may (and do) behave differently and that might make tests break (or pass and then
break in production). PostgreSQL is the suggested db for production.

After setting up the db, you should run

```
(env) $ ./manage migrate
```

To create the initial schema. You'll also need to run this from time to time
after pulling other people's code from the VCS repository (as they may have
changed the model).

Running and working with the app locally
========================================

Instead of the standard runserver manage command (./manage runserver) you can
use

```
(env) $ ./manage runserver_plus
```

to run the app. This will enhance the server with the Werkzeug interactive 
debugger that will allow you to interact with your code (debug it) in the
browser, when it throws an exception instead of returning a valid response.

Similarly, instead of ./manage shell you can use

```
(env) $ ./manage shell_plus
```

and have your models (and a few frequently needed classes and modules) be
automatically imported.

Running using docker-compose
============================

```sh
git clone git@github.com:smart-t17/heartface.git
cd backend
docker-compose up -d
```

If ElasticSearch failed to start try running on your Linux:
```sh
sudo sysctl -w vm.max_map_count=262144
```

Wait for application became available and do migration:

```sh
docker exec -ti backend_backend_1 /opt/project/manage migrate
```

Application is available on http://localhost:8000

Postgresql exposed to localhost:15432
Redis exposed to localhost:16379
Elasticsearch exposed to http://localhost:19200

To run ONLY postgresql, redis, elastic run
```sh
docker-compose up -d db redis elasticsearch
```

Installation
============

To install the system first you need to provision a new server
(install and setup external dependencies) then run the deployment
script. To update the app, you just need to run the deployment
again.

Both actions need the development requirements to be installed.

Provisioning
------------

Provisioning is done using ansible (documentation: https://docs.ansible.com/ ). 

The related files are located in the provisioning subdirectory of the project.
The below commands should be run from this directory.

Starting from scratch, e.g. with a vanilla Linode VPS, you do the provisioning
like this (all commands are to be run on your *local* machine):
0. edit hosts file (if you haven't done so far) to include your machines.
1. install your SSH public key to the server using the add-root.sh script:

```
(env) $ ./add-root.sh xxx.xxx.xxx.xxx
```

Where xxx.xxx.xxx.xxx is the IP (or the FQDN) of the target machine

2.

```
(env) $ ./provision_all
```

Without going into the details here's a short explanation for most of the files
used in the provisioning process:
+ hosts - the inventory file containing the hosts we want to provision to.
    Hosts can have different roles (separate db, web server, etc.). This
    simple setup doesn't use this feature.
+ playbook.yml - the provisioning script that describes what and how should
    be installed and set up in the hosts. It will work on debian based systems
    (including ubuntu).
    
    It does roughly the following:
    + add 3rd party repositories for nginx, postgresql and rabbitmq, so
    that it can install up to date versions. (The ones that ship with debian
    are usually too old to be useable.)
    + Install packages need by the app and by its dependencies.
    + create a database user and a database for the app, set the password.
    NOTE: these must match the ones provided in the settings (deployment.py 
    and/or staging.py).
    + Create and set up access rights for the directories to be used by
    the app and the app deploy script. (Note that the rights must be in
    agreement with the user the app will run under, i.e. the setting in
    conf/supervisord_autumn.conf .)
+ files - contains files that get installed during the provisionin step. At
    the moment it holds the nginx (web server) base configuration.
+ roles - this directory is empty, see roles in the [ansible documentation]
    (http://docs.ansible.com/ansible/playbooks_roles.html)
+ pre_requisits.sh - a simple script than installs the pre-requisits needed
    to run ansible on the target machines. (This is not needed for e.g.
    linode VPS machines, as those already have these packages installed.)
+ provision_all - a simple script that executes ansible with the playbook.yml
    and the hosts inventory file, thus provisioning all hosts that are
    listed in the hosts file
+ add-root.sh - a simple convenience script to add the ssh public key (RSA) of
    the current user to the root account of the specified machine. This is needed
    to avoid ansible constantly asking for a password. (The key can be added in
    any other way, of course.)
+ test - contains files and a script that allows running the whole process on
    Docker, creating a docker image as a result. Theoretically this could be
    used as a deployment format as well (though the app itself is NOT included
    at this step yet), but mainly intended for testing the provisioning process.```


Deployment
----------

The deloyment script should be run against a previously provisioned machine.
The deployment uses fabric (http://www.fabfile.org/).

To install the app on the staging machine run: (see explanation for targets below)
```
(env) $ fab deploy:target=staging
```

Where 'deploy' is the name of the task and the 'target' parameter is set to staging.

This command *has to* be run from the project root directory, where the deployment script
(fabfile.py) is located. The caveat is that it will start from any other subdirectory as well, 
but it will not be able to run without errors.

The deployment script's deploy task does roughly the following:
+ Do a build (build task):
    + put the project files into a tar archive
    + copy (with templating as needed) the config files as described in conf/deploy.map
    into the tar file.
        + For now only a single file is added: the one that selects the environment
        (e.g. staging, deployment), i.e. which setting to use.
    + compress the archive
+ Deploy the archive created by the build:
    + upload the archive into the /tmp dir on the remote machine
    + create a new timestamped subdirectory in the deployment directory (see settings
        at the top of the fabfile).
    + uncompress the uploaded archive there
    + create a virtualenv in the timestamped directory, and use pip to install
        the requirements matching the environment (see the target parameter above
        and the settings at the top of the fabfile). E.g.: staging or deployment
    + run collectstatic and migrations
    + upload the nginx and the supervisor config files. (Note, that "supervisorct reload"
        is not being run, thus the changes in the config file won't take effect until
        done so. This may be added to the script.)
    + stop the running instance of the app (which was the old version up to this point)
    + link 'current' to the timestamped directory we've just deployed into
    + start the app (the new version)
    + tell nginx to reload its config
    
