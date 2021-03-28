If you're running Mac Big Sur and/or your Mac is running on an Apple Silicon chip), 
you must follow the instructions to install for Conda-forge. The instructions for Mac with Intel chip will not work.

[For Conda-forge (Mac with Apple Silicon chip)](docs/INSTALL-conda.md)

[For Mac with Intel chip](docs/INSTALL-mac.md)

[For Linux](docs/INSTALL-linux.md)

[For Windows](docs/INSTALL-windows.md)

### Why are there so many requirements-*.txt?

Koe can run on any operating system, as well as running as a Docker image. So to maximise compatibility, I
created different `requirements.txt` for different environments.

 - `requirements.txt`: contains all the libraries that are necessary to compile and run Koe, except the machine-learning part
 - `requirements-basic.txt`: contains the extra libraries necessary for the machine-learning part of Koe to run on a tensorflow image (CPU-only)
 - `requirements-tensorflow.txt`: contains the extra libraries necessary for the machine-learning part of Koe oto run on a tensorflow image (GPU-enabled)
 - `requirements-conda-forge.txt`: contains the libraries that can be installed by pip in a conda environment
 - `requirements-dev.txt`: contains the extra libraries that are necessary to for development environment, mostly to run lint and profiler
 - `requirements-production.txt`: contains the extra libraries that are necessary to deploy Koe as a webapp (using uWSGI)

#### For dev environment using conda-forge
Many python libraries cannot be installed using pip in conda-forge environment, they must be installed using `conda install`.
The remaining libraries can be installed normally with pip. So for conda-forge the steps to install all python libraries are:
 - First install all the special libraries compiled specifically for conda-forge using `conda install` command
 - Then, install the rest with `pip install requirements-conda-forge.txt`
 - Finally, install the dev tools with `pip install requirements-dev.txt`

#### For dev environment using native CPU
 - First, install all necessary library with `pip install requirements.txt`
 - Finally, install the dev tools with `pip install requirements-dev.txt`

#### For docker image
This section is quite advanced and difficult to get right. 
Also might not be necessary as I'm maintaining an official Koe's Docker image on Docker Hub (https://hub.docker.com/repository/docker/crazyfffan/koe)
So you shouldn't worry about this

