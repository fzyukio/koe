Deploy Koe to a production server
===

# Deployment checklist:
    * [ ] Activate virtual environment      
    * [ ] Prepare your server
      * [ ] Install docker
      * [ ] Prepare the environment
      * [ ] Now compile for production
      * [ ] Build and run the image

## Activate the environment
On Windows:
```shell
.venv\Scripts\activate.bat
```

On Mac or Linux:
```shell
.venv/bin/activate
```

## Prepare your server

### Install docker
You need both `docker` and `docker-compose` installed. Versions that work for me are: `docker-compose 1.20.1` and `docker 18.09.5`

See https://docs.docker.com/install/ and https://docs.docker.com/compose/install/

### Prepare the environment
- Check out the repo, then make a copy of `settings.default.yaml`, name it `settings.yaml`.
- Add `secret_key` to the end of this file.
- Change the following settings:
  - `debug` to `False`
  - Add the domain of your website to `allowed_hosts` (if you have such domain)
  - Likewise, change `site_url` and `csrf_trusted_origin` to include this domain
  - Set `session_cookie_secure` to `True` if your domain supports HTTPS

- Make a `.env` file with the following content:
```bash
DOCKER_FILE=Dockerfile-basic

CONTAINER_DATABASE_NAME=koe_db
CONTAINER_APP_NAME=koe_app
CONTAINER_CACHE_NAME=koe_cache

DJANGO_SETTINGS_MODULE=koe.settings

MYSQL_HOST=koe_db
MYSQL_ROOT_PASSWORD=root
MYSQL_USER=koe
MYSQL_PASSWORD=koe
MYSQL_DATABASE=koe
MYSQL_VOLUME=../koe-db

EXTERNAL_NETWORK=nginx-server_web

DB_PORT=127.0.0.1:3308:3306
EXPOSED_PORTS=0.0.0.0:8000-8000:8000-8000

runtime=runc
```

  - Change mysql username/password if you like, if you do, change `database_url` in `settings.yaml` accordingly
  - Change `EXTERNAL_NETWORK` if you already have a `docker network` container
  - If you want `tensorflow` and `jupyter` support:
    - Change `DOCKER_DOCKER_FILE=Dockerfile.basic` to `DOCKER_FILE=Dockerfile-tensorflow`
    - Change `runtime=runc` to `runtime=nvidia`

### Now compile for production on your development machine

Your production server can be the same as your developement machine - but if your server is on the cloud, it is
recommended to compile things on your computer.
```bash
yarn build-prod
python manage.py collectstatic -v 0 --noinput
```

Then copy the compiled assets, which include: `assets/bundles` `static` `jquery-webpack-stats.json` `webpack-stats.json`
to the server

### Build and run the image
```bash
docker-compose build
docker-compose up -d
```
