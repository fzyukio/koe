# Django-grid

This project is folked from https://github.com/vintasoftware/django-react-boilerplate
Substantial changes include:
- Upgrade to Django 2.0.1 (which is Python 3 exclusive)
- Out-of-the-box grid management using Slickgrid on the client side
- The model is fully compatible with MySql, Postgre and Sqlite

## Setup
### First, make sure you have all the dependencies installed.

List of important dependencies:
- Python 3
- ffmpeg
- mysql
- postgre (if use postgre)
- sqlite3 (if use sqlite3)
- virtualenv
- nodejs (>=9.0)
- redis

#### For Debian/Ubuntu
```shell
sudo ./setup-ubuntu.sh
sudo ./install-redis.sh
```

#### For Mac:
```
Figure it out yourself
```

### Install virtualenv, then
```
cd /path/to/project/
virtualenv -p `which python3` .venv
```

Add the following lines in `.venv/bin/activate`:
```bash
export DJANGO_SETTINGS_MODULE=koe.settings.production
export SECRET_KEY='????????????????????????????????????????????'
export ALLOWED_HOSTS='*'
export EMAIL_CONFIG=in-v3.mailjet.com:306f80c638198c7284dd3833162cc881:7e9618e6955c3672aa86fa353fec74ba:587
export FROM_EMAIL='fa@io.ac.nz'
export REDIS_PORT=6379
export REDIS_HOST=localhost
export REDIS_URL='redis://'
export REDIS_PASSWORD=''
export PATH=$PATH:/usr/local/bin/
export FFMPEG=/usr/local/bin/ffmpeg
export WEBPACK_SERVER_PORT=9876
## Database config
#DB_TYPE=sqlite3
DB_TYPE=mysql
#DB_TYPE=postgresql

if test "$DB_TYPE" = "sqlite3"; then
    export DB_ENGINE=django.db.backends.sqlite3
    export DB_NAME=koe.db
    export DB_USER=''
    export DB_PASSWORD=''
    export DB_PORT=''
    export DB_HOST=''
elif test "$DB_TYPE" = "postgresql"; then
    export DB_ENGINE=django.db.backends.postgresql
    export DB_NAME=yfukuzaw
    export DB_USER='yfukuzaw'
    export DB_PASSWORD=''
    export DB_PORT='5444'
    export DB_HOST='localhost'
elif test "$DB_TYPE" = "mysql"; then
    export DB_ENGINE=django.db.backends.mysql
    export DB_NAME=koe
    export DB_USER='koe'
    export DB_PASSWORD='koe'
    export DB_PORT=''
    export DB_HOST='localhost'
fi
```

> Note: SECRET_KEY: A random string, use this [tool](https://www.miniwebtool.com/django-secret-key-generator/) to generate one   
> Other variables: change to specific settings if necessary


Then
```bash
source .venv/bin/activate
```

## Install Python dependencies
```bash
pip install numpy
pip install Cython
pip install -r requirements.txt
```

## Install NPM dependencies
```bash
npm install -g webpack
npm install
```

## Initialise the database
> The database must be initialised using this script.

```bash
./migrate.sh # Every time this runs it will drop the entire database and create a new one
```

## Build for development
```bash
yarn build
yarn start # This command will run the server at port specified by $WEBPACK_SERVER_PORT
```


## Build for production
```bash
yarn build-prod # Compile Javascript and SCSS
python manage.py collectstatic --noinput # Collect static files to /static/
```

## Quick way to deploy on server:
You should fully deploy your app if there is any Javascript change - as these need to be compiled and package by webpack
To run this app on the server, config nginx or apache accordingly. The following scripts is written to deploy the app using gunicorn.

Change file `deploy.sh` and `deploy-hot.sh` at the following lines:
```bash
REMOTE_ADDRESS=123.123.123.123
REMOTE_USER=remote_user
WORKSPACE=/path/to/project/on/server
SSH_EXTRA_CREDENTIAL='-i /path/to/credential.pem' # Leave empty if not necessary
APP_NAME=app_name
```

Run `deploy.sh` to fully deploy to the server
Run `deploy-hot.sh` to simply pull the new, committed code onto the server workspace and restart the webserver

# Licence
MIT

TL;DR: You can do what the hell you want with this, as long as you credit me and not hold me responsible for any problem whatsoever.

Copyright (c) 2013-9999 Yukio Fukuzawa

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
