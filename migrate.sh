#!/usr/bin/env bash

#echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | python manage.py dbshell

rm koe.db

python manage.py makemigrations root;
python manage.py makemigrations koe;
python manage.py migrate --database=default

function run() {
  echo "Running fixture: $1"
  python manage.py loaddata koe/fixtures/$1.json
}

#run auth
run users
#run data
