#!/bin/bash

unset http_proxy
unset https_proxy

cd /code

if test "$CLEAR_DB" = "true"; then
    # drop all tables
    QUERY_TO_RUN=`echo "SELECT concat('DROP TABLE IF EXISTS ', table_name, ';') FROM information_schema.tables WHERE table_schema = '${DB_NAME}'" | python manage.py dbshell`
    DELETE_QUERY=`echo "$QUERY_TO_RUN" |  sed -n '1!p'`
    echo "SET FOREIGN_KEY_CHECKS = 0;${DELETE_QUERY}SET FOREIGN_KEY_CHECKS = 1;ALTER DATABASE ${DB_NAME} CHARACTER SET utf8; " | python manage.py dbshell
fi

# Important: This flag must be set for this to work
export IMPORTING_FIXTURE="true"
python manage.py migrate

if test "$CLEAR_DB" = "true"; then
    # load all fixtures - must be done in this order
    python manage.py loaddata users
    python manage.py loaddata cms
    python manage.py loaddata data
    python manage.py loaddata root.columnactionvalue.json
    python manage.py loaddata root.extraattr.json
    python manage.py loaddata root.extraattrvalue.json
fi
export IMPORTING_FIXTURE="false"

python manage.py collectstatic --noinput

uwsgi --ini uwsgi.ini:prod


