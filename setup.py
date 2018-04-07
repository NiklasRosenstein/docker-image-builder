
import setuptools

with open('requirements.txt') as fp:
  install_reqs = fp.readlines()

setuptools.setup(
  name = 'docker-image-builder',
  version = '1.0.0',
  author = 'Niklas Rosenstein',
  author_email = 'rosensteinniklas@gmail.com',
  license = 'MIT',
  description = 'A simplistic API for creating scripts that build Docker images.',
  packages = setuptools.find_packages(),
  install_reqs = install_reqs
)
