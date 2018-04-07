# The MIT License (MIT)
#
# Copyright (c) 2018 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
"""
The Docker Image Builder API that can be used from builder scripts.
"""

from . import utils, dockertools
from nr import path

import argparse
import contextlib
import docker
import io
import json
import os
import posixpath
import uuid
import shlex
import sys
import tarfile

if not hasattr(shlex, 'quote'):
  import pipes
  shlex.quote = pipes.quote

client = docker.from_env()
client.ping()

parser = argparse.ArgumentParser()
add_argument = parser.add_argument
parse_args = parser.parse_args

container = None
buildtime_volumes = {}
_workdir = None
_cmd = None
_entrypoint = None
_user = None
_expose = []
_volumes = []


def error(message, code=1):
  print(message, file=sys.stderr)
  sys.exit(code)


@contextlib.contextmanager
def new(image, command=['sleep', '999999999'], **kwargs):
  """
  Create a new container from the base image *image*. The default command is
  "sleep infinity" which will make the container sleep forever, allowing us
  to execute commands while it is idle.

  This function returns a context-manager that will automatically stop and
  remove the container. Make sure to create an image from the container
  using the #commit() function.
  """

  global container
  if container:
    raise RuntimeError('new() can not be nested')

  kwargs['volumes'] = utils.merge_dictionary(
    buildtime_volumes, kwargs.get('volumes', {}))

  name = 'dib-temp-' + str(uuid.uuid4())[:8]
  try:
    container = client.containers.run(image, command, name=name,
      auto_remove=True, detach=True, **kwargs)
    yield
  finally:
    if container:
      try:
        container.kill()
      except docker.errors.APIError:
        pass
    container = None

    global _workdir, _cmd, _entrypoint, _user, _expose
    _workdir = None
    _cmd = None
    _entrypoint = None
    _user = None
    _expose = []


def run(cmd, **kwargs):
  """
  Uses #docker.Container.exec_run() to execute a command in the current
  container.
  """

  if not container:
    raise RuntimeError('no current container')

  cmd_str = cmd if isinstance(cmd, str) else ' '.join(map(shlex.quote, cmd))
  print('RUN', cmd_str)
  print()

  if isinstance(cmd, str):
    cmd = ['bash', '-c', cmd]

  if _workdir and 'workdir' not in kwargs:
    kwargs['workdir'] = _workdir

  result = dockertools.container_exec(container, cmd, stream=True, **kwargs)
  res = result.communicate(line_prefix=b'    ')
  print()

  if res != 0:
    error('ERROR exit code {!r}'.format(res))


def buildtime_volume(host_path, container_path, mode='rw'):
  """
  Add a volume to be mounted at build time. This needs to be called before
  entering a container build context with #new(). Calling this function from
  inside #new() causes a #RuntimeError.
  """

  if container:
    raise RuntimeError('buildtime_volume() can not be used from inside a build context')

  seps = [path.sep]
  if os.name == 'nt':
    seps.append('/')

  if not path.isabs(host_path) and (host_path.startswith(path.curdir) or
      host_path.startswith(path.pardir) or any(x in host_path for x in seps)):
    host_path = path.abs(host_path)

  buildtime_volumes[host_path] = {'bind': container_path, 'mode': mode}


def workdir(path):
  """
  Sets the current working directory. Can only be used inside a build
  context entered with #new().
  """

  if not container:
    raise RuntimeError('workdir() can not be used outside of a build context')

  global _workdir
  _workdir = path
  print("WORKDIR", shlex.quote(path))


def cmd(cmd):
  """
  Sets the CMD of the current container. Note that you need to call #commit()
  in the end.
  """

  if not container:
    raise RuntimeError('cmd() can not be used outside of a build context')

  if isinstance(cmd, str):
    cmd = ['bash', '-c', cmd]

  global _cmd
  _cmd = cmd


def entrypoint(cmd):
  """
  Sets the ENTRYPOINT of the current container.
  """

  if not container:
    raise RuntimeError('entrypoint() can not be used outside of a build context')

  if isinstance(cmd, str):
    cmd = ['bash', '-c', cmd]

  global _entrypoint
  _entrypoint = cmd


def user(name, group=None):
  """
  Sets the USER of the current container.
  """

  if not container:
    raise RuntimeError('user() can not be used outside of a build context')

  global _user
  if group:
    _user = '{}:{}'.format(name, group)
  else:
    _user = name


def expose(decl):
  """
  Adds an EXPOSE entry to the current container.
  """

  if not container:
    raise RuntimeError('expose() can not be used outside of a build context')
  _expose.append(decl)


def volume(decl):
  """
  Declares a VOLUME in the current container.
  """

  if not container:
    raise RuntimeError('expose() can not be used outside of a build context')
  _volumes.append(decl)


def commit(repository=None, tag=None, author=None, message=None, conf=None):
  """
  Commits the container. *label* must be the repository and optionally
  the tag in the format `REPOSITORY:[TAG]`.
  """

  if not container:
    raise RuntimeError('commit() can not be used outside of a build context')

  if repository:
    repository, implicit_tag = repository.partition(':')[::2]
    if implicit_tag and not repository:
      raise ValueError('tag without repository')
    if tag and implicit_tag:
      raise ValueError('tag in repository and tag argument')
    tag = implicit_tag
  else:
    repository, tag = None, None

  changes = []
  if _cmd is not None:
    changes.append('CMD ' + json.dumps(_cmd))
  if _entrypoint is not None:
    changes.append('ENTRYPOINT ' + json.dumps(_entrypoint))
  if _user is not None:
    changes.append('USER ' + _user)
  if _workdir is not None:
    changes.append('WORKDIR ' + json.dumps(_workdir))
  for port in _expose:
    changes.append('EXPOSE ' + port)
  for vol in _volumes:
    changes.append('VOLUME ' + vol)

  return container.commit(repository=repository, tag=tag, message=message,
    author=author, changes=changes, conf=conf)


def copy(src, dst, crlf_to_lf=False, chmod=''):
  if _workdir:
    dst = posixpath.normpath(posixpath.join(_workdir, dst))
    print()
    print('@@@', dst)
    print()
  buffer = io.BytesIO()
  with tarfile.open(fileobj=buffer, mode='w') as tar:
    if crlf_to_lf and not path.isfile(src):
      raise RuntimeError('crlf_to_lf=True, but "{}" is not a file'.format(src))
    if crlf_to_lf:
      with open(src, 'rb') as fp:
        content = fp.read().replace(b'\r\n', b'\n')
      tf = tarfile.TarInfo(path.base(src))
      tf.mode = path.chmod_update(os.stat(src).st_mode, chmod)
      tf.size = len(content)
      tar.addfile(tf, io.BytesIO(content))
    else:
      tar.add(src, path.base(src), recursive=True)
  if not container.put_archive(dst, buffer.getvalue()):
    raise RuntimeError('put_archive() failed')


class apt:
  """
  Helper that run APT commands.
  """

  @staticmethod
  def clean():
    """
    Cleanup any cache files. Useful after installing stuff so that it does
    not stick around in the container image.
    """

    run('rm -rf /var/lib/apt/lists/*')

  @staticmethod
  def update():
    run(['apt-get', 'update'])

  @staticmethod
  def install(*packages, yes=True):
    cmd = ['apt-get', 'install']
    if yes:
      cmd += ['-y']
    cmd += packages
    run(cmd)


class apk:
  """
  Helper for running APK commands.
  """

  @staticmethod
  def clean():
    run('rm -rf /var/cache/apk/* /var/cache/distfiles/*')

  @staticmethod
  def update():
    run('apk update')

  @staticmethod
  def add(*packages):
    run(['apk', 'add'] + list(packages))
