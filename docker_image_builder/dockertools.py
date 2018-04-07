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
Stuff that the Python docker module can't do.
"""

import sys


def container_exec(container, cmd, stdout=True, stderr=True, stdin=False,
                   tty=False, privileged=False, user='', detach=False,
                   stream=False, socket=False, environment=None, workdir=None):
  """
  An enhanced version of #docker.Container.exec_run() which returns an object
  that can be properly inspected for the status of the executed commands.
  """

  exec_id = container.client.api.exec_create(
    container.id, cmd, stdout=stdout, stderr=stderr, stdin=stdin, tty=tty,
    privileged=privileged, user=user, environment=environment,
    workdir=workdir)['Id']

  output = container.client.api.exec_start(
    exec_id, detach=detach, tty=tty, stream=stream, socket=socket)

  return ContainerExec(container.client, exec_id, output)


class ContainerExec(object):

  def __init__(self, client, id, output):
    self.client = client
    self.id = id
    self.output = output

  def inspect(self):
    return self.client.api.exec_inspect(self.id)

  def poll(self):
    return self.inspect()['ExitCode']

  def communicate(self, line_prefix=b''):
    for data in self.output:
      if not data: continue
      offset = 0
      while offset < len(data):
        sys.stdout.buffer.write(line_prefix)
        nl = data.find(b'\n', offset)
        if nl >= 0:
          slice = data[offset:nl+1]
          offset = nl+1
        else:
          slice = data[offset:]
          offset += len(slice)
        sys.stdout.buffer.write(slice)
      sys.stdout.flush()
    while self.poll() is None:
      raise RuntimeError('Hm could that really happen?')
    return self.poll()
