#!/bin/bash

unset http_proxy
unset https_proxy

cd /code

IS_TENSORFLOW=$1

python maintenance.py --probe-database

# Always back-up the database
mkdir -p backups/mysql
chmod 777 backups/mysql
DB_BACKUP_NAME=backups/mysql/backup-`date "+%Y-%m-%d_%H-%M-%S"`.sql
python maintenance.py --backup-database --file="$DB_BACKUP_NAME"
chmod 666 "$DB_BACKUP_NAME"

if test "$RESET_DB" = "true"; then
    python maintenance.py --reset-database
else
    python manage.py migrate --database=default
fi

# Always clear the cache
python manage.py cache --action=clear --pattern='template.cache.*'

celery -A koe worker -l info -c 1 --logfile=logs/celery.log&
sleep 1
python manage.py resume_unfinished_task

if [ "$IS_TENSORFLOW" = "tensorflow" ]; then
  python manage.py shell_plus --notebook &
  uwsgi --ini uwsgi.ini:tensorflow
else
  uwsgi --ini uwsgi.ini:prod
fi
