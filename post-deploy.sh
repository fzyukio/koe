#!/usr/bin/env bash
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



NAME="koe"                                  # Name of the application
DJANGODIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"             # Django project directory
SOCKFILE=${DJANGODIR}/gunicorn.sock  # we will communicte using this unix socket
USER=`whoami`                                        # the user to run as
GROUP=`id -gn`                                     # the group to run as
NUM_WORKERS=3                                     # how many worker processes should Gunicorn spawn
DJANGO_SETTINGS_MODULE=koe.settings             # which settings file should Django use
DJANGO_WSGI_MODULE=koe.wsgi                     # WSGI module name

echo "Starting $NAME as $USER"
echo "Current Dir is $DJANGODIR"

cd ${DJANGODIR}

# Activate the virtual environment
source .venv/bin/activate
echo -e "${Black}${On_White}Run migrate${Color_Off}"
.venv/bin/python manage.py migrate --database=default
echo -e "${Black}${On_White}Collect static${Color_Off}"
.venv/bin/python manage.py collectstatic --noinput
#export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
#export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
echo -e "${Black}${On_White}Run the app${Color_Off}"
nohup .venv/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user=$USER \
  --group=$GROUP \
  --bind=unix:$SOCKFILE \
  --log-level=debug \
  --log-file=gunicorn.log \
  > out.log 2> err.log < /dev/null &