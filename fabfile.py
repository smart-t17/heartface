# Generic tools, move this into a separate lib, later opensource
import contextlib
from functools import wraps, update_wrapper
import datetime
import shutil
from enum import Enum
import re
import os
from tempfile import NamedTemporaryFile
from fabric.context_managers import settings, lcd, cd, hide, show, shell_env
from fabric.decorators import task
from fabric.operations import local, run, put
from fabric.state import env
from fabric.tasks import execute, WrappedCallableTask
from formic import formic
from slacker import Slacker

DEFAULT_TARGET_PARAM = 'target'

CONFIG = {
    'DEFAULT': {
        # Not used yet
        'version_file': 'VERSION',
        'timestamp_format': '%Y-%m-%d-%H-%M-%S',
    },
    'test': {
        'env_name': 'test',
        'hosts': ['root@']
    },
    'dev': {
        'hosts': ['root@heartface.atleta.hu'],
        'dest': '/usr/local/lib/heartface/',
        'env_name': 'dev',
        'requirements': 'deployment',
        'static': '/var/www/heartface'
    },
    'staging': {
        'hosts': ['root@dev.heartface.tv'],
        'dest': '/usr/local/lib/heartface/',
        'env_name': 'staging',
        'requirements': 'deployment',
        'static': '/var/www/heartface'
    },
    'production': {
        'hosts': ['root@prod.heartface.tv'],
        'dest': '/usr/local/lib/heartface/',
        'env_name': 'deployment',
        'requirements': 'deployment',
        'static': '/var/www/heartface'
    },
}

_TASKS_EXECUTED = set()

class FabricException(Exception):
    pass

def config_for_target(target):
    config = CONFIG['DEFAULT']
    config.update(CONFIG[target])
    return config

# TODO: add default target
def configure(func,target_param=DEFAULT_TARGET_PARAM):
    # TODO: (when making a lib) could be imported from six as well
    def decorator(*args, **kwargs):
        if 'target_env' in env:
            execute(func, *args, **kwargs)
        else:
            target = kwargs.pop(target_param)
            config = config_for_target(target)
            config['target_env'] = target

            with settings(**config):
                execute(func, *args, **kwargs)

    return WrappedCallableTask(update_wrapper(decorator, func))

def depends(deps):
    def inner(func):
        func.deps = deps
        def decorator(*args, **kwargs):
            for dependency in func.deps:
                if not dependency in _TASKS_EXECUTED:
                    _TASKS_EXECUTED.add(dependency)
                    dependency(*args, **kwargs)
            return func(*args, **kwargs)

        return WrappedCallableTask(update_wrapper(decorator, func))
    return inner

@contextlib.contextmanager
def noop_context():
    yield

class FileMapping(object):
    """Mapping file parser for FileInstaller.
    The map file can use templating (jinja2). Templates will be evaluated before the
    actual parsing. Lines starting with # are treated as comments (and thus ignored).

    TODO: maybe use formic patterns?
    """
    class Entry(object):
        """A single entry describing the mapping for a single file.

        An entry looks like this:
        * simple file installation:
        <local_path> -> <remote_path> [<remote_mode>[,<remote_owner>[.<remote_group>]]]

        * file installation with template rendering:
        <local_path> => <remote_path> [<remote_mode>[,<remote_owner>[.<remote_group>]]]

        * remote link creation
        <remote_path> ~> <remote_path>
        """
        TYPE = Enum('EntryType', 'copy template link')
        __TYPE_MAP = {'-': TYPE.copy, '=': TYPE.template, '~': TYPE.link}

        def __init__(self, source, dest, type, mode=None, owner=None,group=None):
            self.source = source
            self.dest = dest
            self.type = self.__TYPE_MAP[type]
            self.mode = mode
            self.owner = owner
            self.group = group

    COMMENT_RX = re.compile(r'^\s*#.*$')
    __NAME_RX = r'[a-z][-a-z0-9]*'
    ENTRY_PARSER_RX = re.compile(r'\s*(?P<source>[^ ]+)\s+(?P<type>[\-~=])>\s+(?P<dest>[^ ]+)'
        '(?:\s+(?P<mode>[0-7]4)(?:,(?P<owner>{name_rx})?(?:\.(?P<group>{name_rx}))?)?)?\s*$'
                                 .format(name_rx = __NAME_RX))

    def __init__(self, mapping_file):
        """
        @param mapping_file: Mapping file to read mapping from. (Either the file name or a
        'file-like' object having a readlines() method.)
        @type mapping_file: basestring|file
        """
        if isinstance(mapping_file, str):
            with open(mapping_file) as f:
                self.__parse(f)
        else:
            self.__parse(mapping_file)

    def __parse(self, map):
        self.entries = []

        for cnt, line in enumerate(map.readlines()):
            if not self.COMMENT_RX.match(line):
                values = self.ENTRY_PARSER_RX.match(line.strip())

                if values:
                    self.entries.append(self.Entry(**values.groupdict()))
                else:
                    raise ValueError('Syntax error on line %d: %s' % (cnt, line))

class FileInstaller(object):
    """Install files using a map file."""
    # python stupidity... see real definition at the end of the class
    _TYPE_HANDLERS = {}

    @classmethod
    def install(cls, mapping, base_dir=None, dest_dir='.', context={}):
        """Install files as described by the specified mapping. At least one of base_dir or
        dest_dir should be specified.

        NOTE: ownership parameters are currently ignored.

        @param mapping: Parsed mapping
        @type mapping: FileMapping
        @param base_dir: the base directory which is used for interpreting relative paths in the
        mapping.
        @type base_dir: basestring
        @param dest_dir: the directory where the installation files go to. (All target paths are
          created under this directory.) dest_dir is either absolute or is interpreted as relative
          to base_dir.
        @type dest_dir: basestring
        @param context: context to use for
        @return: The list of files/links created (with paths relative to dest_dir)
        """
        result = []
        with lcd(base_dir) if base_dir else noop_context():
            for entry in mapping.entries:
                dest = os.path.join(dest_dir, entry.dest)
                if dest[:-1] == os.path.sep:
                    dest = os.path.join(dest, os.path.basename(entry.source))

                dest_file_dir = os.path.dirname(dest)
                local('mkdir -p %s' % dest_file_dir)
                cls._TYPE_HANDLERS[entry.type](entry.source, dest, context)
                if entry.mode:
                    # TODO: consider using shutils
                    local('chmod %s %s' % (entry.mode, dest))
                    # TODO: generate script to change ownership AND update the specified tar file,
                    # then run it under fakeroot (might work...)
                result.append(dest[len(dest_dir)+1:])

        return result

    @classmethod
    def copy_file(cls, source,dest, _):
        shutil.copy(source, dest)

    @classmethod
    def copy_template(cls, source, dest, context):
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader('.'))
        with open(dest, 'w+') as out:
            out.write(env.get_template(source).render(context))

    @classmethod
    def create_link(cls, source, dest, _):
        local('ln -sfn %s %s' % (source, dest))

# Boy, is this lame...
FileInstaller._TYPE_HANDLERS = {
    FileMapping.Entry.TYPE.copy: FileInstaller.copy_file,
    FileMapping.Entry.TYPE.template: FileInstaller.copy_template,
    FileMapping.Entry.TYPE.link: FileInstaller.create_link,

}

def tar(files,file_name,update=False):
    """
    Create/update tar archive.
    """
    mode = 'r' if update else 'c'
    with NamedTemporaryFile(mode='w+', delete=False) as list_file:
        cwd = os.getcwd()
        list_file.write('\n'.join(f[len(cwd) + 1:] if f.startswith(cwd) else f for f in files))
        list_file.flush()
        local('tar {mode}f {arch_name} -T {list}'.format(
            mode=mode, arch_name=file_name, list=list_file.name
        ))
#
# Task definitions
#

@configure
@task
def build(patch=False):
    # TODO: use fakeroot when building the archive (if needed)
    local('rm -rf build/*')
    local('mkdir -p build')

    app_files = formic.FileSet(
        include=[
            '/requirements/**', '/heartface/**', '/static/**', '/templates/**', '/manage', '/scrapy.cfg', '/crawlers/**',
        ], exclude=[
            '/heartface/settings/environment.py', '*.pyc'
        ]
    )

    # git filtering is disabled for now, as the front end is not part of this repo AND no way to find errors
    # caused by missing files without testing
    tar(app_files, 'build/deploy.tar')

    generated = FileInstaller.install(FileMapping('deploy.map'), dest_dir='build', context=env)

    with lcd('build'):
        tar(generated, 'deploy.tar', update=True)

        # NOTE: better compression doesn't yield enough speedup on uploading to make up for the
        #  slower compressor run time
        local('gzip deploy.tar')

@configure
@depends([build])
@task
def deploy():
    timestamp = datetime.datetime.utcnow().strftime(env.timestamp_format)
    version = local('git rev-parse HEAD', capture=True).stdout.strip()
    version_timestamp = local('git log -1 --pretty=format:%ct', capture=True).stdout.strip()

    run('mkdir -p %s' % env.dest)
    with cd(env.dest):
        with settings(abort_exception=FabricException):
            try:
                old_version = run('cat current/VERSION', warn_only=False).stdout.strip().split()[0]
            except FabricException:
                old_version = 'HEAD'

        run('mkdir %s' % timestamp)
        with cd(timestamp):
            remote_archive = '/tmp/heartface-%s-%s.tar.gz' % (timestamp, version)
            # TODO: use rsync in a '3-way' mode (--link-dest) to minimize files transfered
            #  (do the same for the locally built virtualenv)
            put('build/deploy.tar.gz', remote_archive)
            # TODO: remove --no-same-owner when built with fakeroot
            run('tar xfz %s --no-same-owner' % remote_archive)
            run('rm %s' % remote_archive)
            run('echo %s %s > VERSION' % (version, version_timestamp))

            with hide('stdout'):
                run('virtualenv -p python3 env')

                # NOTE: Temporary solution: install through running pip remotely
                # run('env/bin/pip install pip-accel')
                # run('env/bin/pip-accel install -r requirements/%s.txt' % env.requirements)
                run('env/bin/pip install -U pip')
                run('env/bin/pip install -r requirements/%s.txt' % env.requirements)

                with show():
                    run('env/bin/python manage migrate')
                    run('env/bin/python manage create_indexes')

                # NOTE: take it from the settings...
                run('mkdir assets')
                # NOTE: can also be run locally
                run('env/bin/python manage collectstatic -v 0 -l --noinput -c')

        run('systemctl stop celery-worker')
        run('systemctl stop celery-beat')
        run('systemctl stop flower')
        run('systemctl stop uwsgi')
        run('ln -sfn %s current' % timestamp)
        run('systemctl start uwsgi')
        run('systemctl start flower')
        run('systemctl start celery-beat')
        run('systemctl start celery-worker')

        slack = Slacker("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        hosts = ','.join(h.split('@')[1] for h in env.hosts)

        all_logs = local('git log %s..%s' % (old_version, version), capture=True).stdout.strip()
        merge_logs = local('git log --merges %s..%s' % (old_version, version), capture=True).stdout.strip()
        slack.chat.post_message(
            'backend', "A new version of the backend has been deployed to %s.\n  commit id: %s" % (hosts, version),
            attachments=[
                {
                    'title': 'Merged branches',
                    'color': 'warning',
                    'text': merge_logs
                },
                {
                    'title': 'All commits',
                    'text': all_logs
                }
            ]
        )


@configure
@depends([build])
@task
def test():
    print('Test')

@task
def rebuild_db():
    """Drop and re-sync the app specific tables from the db, load dev fixtures"""
    local('bin/drop_model')
    local('./manage syncdb')
    local('./manage loaddata tests/fixtures.json')
