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

CFG_FILE=$1

echo -e "${Yellow}${On_Purple}Remove old asset bundles before building a new one.${Color_Off}"
echo -e "${Green}${On_Black}rm -rf assets/bundles static${Color_Off}"
rm -rf assets/bundles static

echo -e "${Yellow}${On_Purple}build-prod will compile javascript, sass and give them a hash,${Color_Off}"
echo -e "${Yellow}${On_Purple} so the files can be served as static${Color_Off}"
echo -e "${Green}${On_Black}yarn build-prod${Color_Off}"
yarn build-prod
echo -e "${Green}${On_Black}DEBUG=false python manage.py collectstatic --noinput${Color_Off}"

DEBUG=false python manage.py collectstatic --noinput

RESULT=$?
if [ $RESULT -eq 0 ]; then

    echo -e "${Yellow}${On_Purple}Now package the generated files to be copied over${Color_Off}"
    echo -e "${Green}${On_Black}docker-compose build${Color_Off}"
    docker-compose build
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi
