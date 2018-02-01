#!/bin/bash

# Install the Build and Test Dependencies
sudo apt-get update
sudo apt-get install -y curl build-essential tcl

# Download and Extract the Source Code
cd /tmp
curl -O http://download.redis.io/redis-stable.tar.gz
tar xzvf redis-stable.tar.gz
cd redis-stable

# Build and Install Redis
make
make test
sudo make install

# Configure Redis
sudo mkdir /etc/redis
sudo cp /tmp/redis-stable/redis.conf /etc/redis
sudo sed -i "s/^supervised no/supervised systemd/" /etc/redis/redis.conf
sudo sed -i "s/^dir \.\//dir \/var\/lib\/redis/" /etc/redis/redis.conf

# Create a Redis systemd Unit File
sudo cp redis.service /etc/systemd/system/redis.service

# Create the Redis User, Group and Directories
sudo adduser --system --group --no-create-home redis
sudo mkdir /var/lib/redis
sudo chown redis:redis /var/lib/redis
sudo chmod 770 /var/lib/redis

# Start Redis
sudo systemctl start redis

# Enable Redis to Start at Boot
sudo systemctl enable redis

# Clean
rm -rf /tmp/redis-stable
rm /tmp/redis-stable.tar.gz
