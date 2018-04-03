#!/bin/bash

# Reset
Color_Off='\033[0m'       # Text Reset

# Regular Colors
Black='\033[0;30m'        # Black
Red='\033[0;31m'          # Red
Green='\033[0;32m'        # Green
Yellow='\033[0;33m'       # Yellow
Blue='\033[0;34m'         # Blue
Purple='\033[0;35m'       # Purple
Cyan='\033[0;36m'         # Cyan
White='\033[0;37m'        # White

# Background
On_Black='\033[40m'       # Black
On_Red='\033[41m'         # Red
On_Green='\033[42m'       # Green
On_Yellow='\033[43m'      # Yellow
On_Blue='\033[44m'        # Blue
On_Purple='\033[45m'      # Purple
On_Cyan='\033[46m'        # Cyan
On_White='\033[47m'       # White

source .venv/bin/activate

echo -e "${Yellow}${On_Purple}You're in `pwd` ${Color_Off}"

if test "$DB_ENGINE" = "django.db.backends.sqlite3"; then
    echo -e "${Yellow}${On_Purple}You are running SQLite database. I'm resetting it to empty${Color_Off}"
    rm ${DB_NAME}
elif test "$DB_ENGINE" = "django.db.backends.postgresql"; then
    echo -e "${Yellow}${On_Purple}You are running Postgre database. I'm resetting it to empty${Color_Off}"
    echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" | python manage.py dbshell
elif test "$DB_ENGINE" = "django.db.backends.mysql"; then
    echo -e "${Yellow}${On_Purple}You are running Mysql database. I'm resetting it to empty${Color_Off}"
    QUERY_TO_RUN=`echo "SELECT concat('DROP TABLE IF EXISTS ', table_name, ';') FROM information_schema.tables WHERE table_schema = '${DB_NAME}'" | python manage.py dbshell`
    DELETE_QUERY=`echo "$QUERY_TO_RUN" |  sed -n '1!p'`
    echo "SET FOREIGN_KEY_CHECKS = 0;${DELETE_QUERY}SET FOREIGN_KEY_CHECKS = 1;ALTER DATABASE ${DB_NAME} CHARACTER SET utf8; " | python manage.py dbshell
fi

echo -e "${Yellow}${On_Purple}Running migration scripts${Color_Off}"

python manage.py makemigrations koe;
python manage.py makemigrations root;
python manage.py migrate --database=default

function run() {
  echo "Running fixture: $1"
  python manage.py loaddata koe/fixtures/$1.json
}

echo -e "${Yellow}${On_Purple}Importing fixtures...${Color_Off}"
#run auth
run users
run cms
run data
run root.columnactionvalue
run root.extraattr
run root.extraattrvalue
