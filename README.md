# docker-image-builder

A simplistic Python package to make it easier to build Docker images in
cases where a Dockerfile is not sufficient (eg. when you want to mount
volumes at build time).

__Example__

```python
import docker_image_builder.api as dib

dib.add_argument('--installer', required=True,
  help='The location of the installer to mount during build time.')

args = dib.parse_args()

dib.buildtime_volume(args.installer, '/tmp/installer')

with dib.new('ubuntu:lastest'):
  dib.apt.update()
  dub.apt.install('curl', 'git')
  dib.apt.clean()

  dib.workdir('/tmp/installer')
  dib.run('./install.sh')

  dib.copy('my-entrypoint', '/usr/bin', crlf_to_lf=True)
  dib.cmd('my-entrypoint')
  
  dib.commit('niklasrosenstein/sometool:2018.4.2')
```

__What it can do__

* Supports same functionality as Dockerfile `FROM`, `WORKDIR`, `RUN`, `USER`,
  `CMD`, `ENTRYPOINT`, `COPY`, `EXPOSE` and `VOLUME` commands
* Mount volumes at build time
* Commit a container as an image

__What it should be able to do in the future__

* Support build layers
