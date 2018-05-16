#!/bin/bash

unset http_proxy
unset https_proxy

cd /code

if test "$CLEAR_DB" = "true"; then
    python setup.py --reset-database
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

uwsgi --ini uwsgi.ini:prod


