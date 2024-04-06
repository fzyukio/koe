#!/usr/bin/env zsh
# Create 1GB Swap
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
sudo swapon --show
sudo cp /etc/fstab /etc/fstab.bak
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl vm.vfs_cache_pressure=50
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.conf

# Install ag, sqlite, ffmpeg
sudo apt-get install silversearcher-ag sqlite3 ffmpeg libxml2-dev libxmlsec1-dev

# Install npm
curl -sL https://deb.nodesource.com/setup_7.x | sudo -E bash -
sudo apt-get install -y nodejs
npm i webpack -g
python manage.py migrate
npm install
npm run build-assets
npm install -g yarn

# Install python, virtualenv
# Install python 3:
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.6 python3.6-dev build-essential
sudo pip install --upgrade pip
sudo pip install --upgrade virtualenv

virtualenv -p `which python` .venv

# nginx
wget https://raw.githubusercontent.com/Angristan/nginx-autoinstall/master/nginx-autoinstall.sh
chmod +x nginx-autoinstall.sh
./nginx-autoinstall.sh

#redis
./install-redis.sh

# Env
echo "export POSTGRESQL_DB_NAME=yfukuzaw" >> .venv/bin/activate
echo "export POSTGRESQL_DB_USERNAME=yfukuzaw" >> .venv/bin/activate
echo "export POSTGRESQL_DB_PASSWORD=\"\"" >> .venv/bin/activate
echo "export POSTGRESQL_DB_HOST=localhost" >> .venv/bin/activate
echo "export POSTGRESQL_DB_PORT=5432" >> .venv/bin/activate
echo "export IS_PRODUCTION=True" >> .venv/bin/activate
echo "export REDIS_HOST=127.0.0.1" >> .venv/bin/activate
echo "export REDIS_PORT=6379" >> .venv/bin/activate

# Make sure there is no requirements missing
source .venv/bin/activate
pip install -r requirements.txt --no-cache-dir --quiet
