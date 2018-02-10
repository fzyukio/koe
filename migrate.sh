#!/usr/bin/env bash
source .venv/bin/activate

echo `pwd`

if test "$DB_ENGINE" = "django.db.backends.sqlite3"; then
    echo "SQLITE"
    rm koe.db
elif test "$DB_ENGINE" = "django.db.backends.postgresql"; then
    echo "POSTGRESQL"
    echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | python manage.py dbshell
elif test "$DB_ENGINE" = "django.db.backends.mysql"; then
    echo "MYSQL"
    QUERY_TO_RUN=`echo "SELECT concat('DROP TABLE IF EXISTS ', table_name, ';') FROM information_schema.tables WHERE table_schema = 'koe'" | python manage.py dbshell`
    DELETE_QUERY=`echo "$QUERY_TO_RUN" |  sed -n '1!p'`
    echo "SET FOREIGN_KEY_CHECKS = 0;${DELETE_QUERY}SET FOREIGN_KEY_CHECKS = 1;ALTER DATABASE koe CHARACTER SET utf8; " | python manage.py dbshell
fi


python manage.py makemigrations koe;
python manage.py makemigrations root;
python manage.py migrate --database=default

function run() {
  echo "Running fixture: $1"
  python manage.py loaddata koe/fixtures/$1.json
}

#run auth
run users
run data
run root.columnactionvalue
run root.extraattr
run root.extraattrvalue
