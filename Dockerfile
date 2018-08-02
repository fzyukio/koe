# Use an official Python runtime as a base image
FROM python:3.6 as koeapp

MAINTAINER Yukio Fukuzawa

ENV PYTHONUNBUFFERED 1

ARG uid=1000

ARG http_proxy=''
ARG https_proxy=''
ENV http_proxy=''
ENV https_proxy=''

# backports needed to install ffmpeg
RUN echo 'deb http://httpredir.debian.org/debian jessie-backports main non-free \n\
deb-src http://httpredir.debian.org/debian jessie-backports main non-free' >> /etc/apt/sources.list

# Install extra packages.
RUN apt-get update && apt-get install -y --no-install-recommends vim mysql-client ffmpeg python-psycopg2 libxml2-dev libxmlsec1-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

## Install any needed packages specified in requirements.txt
RUN pip install Cython numpy && pip install -r requirements.txt --no-cache-dir

# Make port 8000 available to the world outside this container
EXPOSE 8000

WORKDIR /code

COPY . .

ENTRYPOINT ["/bin/bash"]
CMD ["run_koe_app.sh"]
