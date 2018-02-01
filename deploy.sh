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


echo -e "${Yellow}${On_Purple}Remove old asset bundles before building a new one.${Color_Off}"
echo -e "${Green}${On_Black}rm -rf assets/bundles${Color_Off}"
rm -rf assets/bundles

echo -e "${Yellow}${On_Purple}build-prod will compile javascript, sass and give them a hash,${Color_Off}"
echo -e "${Yellow}${On_Purple} so the files can be served as static${Color_Off}"
echo -e "${Green}${On_Black}yarn build-prod${Color_Off}"
yarn build-prod

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Yellow}${On_Purple}Connect to the server and kill the current instance of the website${Color_Off}"
    echo -e "${Yellow}${On_Purple}(we use gunicorn to run)${Color_Off}"
    echo -e "${Green}${On_Black}ssh fzy@174.138.16.121 \"pkill -f gunicorn\"${Color_Off}"
    ssh fzy@174.138.16.121 "pkill -f gunicorn"
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

echo -e "${Yellow}${On_Purple}Also remove all old assets from the remote site${Color_Off}"
echo -e "${Green}${On_Black}ssh fzy@174.138.16.121 \"rm -rf /home/fzy/workplace/koe/assets/bundles /home/fzy/workplace/mossop/static\"${Color_Off}"
ssh fzy@174.138.16.121 "rm -rf /home/fzy/workplace/koe/assets/bundles /home/fzy/workplace/mossop/static"

echo -e "${Yellow}${On_Purple}Make sure the server's code is up-to-date${Color_Off}"
echo -e "${Green}${On_Black}ssh fzy@174.138.16.121 \"cd /home/fzy/workplace/koe; git pull\"${Color_Off}"
ssh fzy@174.138.16.121 "cd /home/fzy/workplace/koe; git pull"

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Yellow}${On_Purple}Now copy the compile bundles over${Color_Off}"
    echo -e "${Yellow}${On_Purple} (We can compile them on the server, but it will be slow)${Color_Off}"
    echo -e "${Green}${On_Black}scp -r assets/bundles fzy@174.138.16.121:/home/fzy/workplace/koe/assets/${Color_Off}"
    scp -r assets/bundles fzy@174.138.16.121:/home/fzy/workplace/koe/assets/
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Green}${On_Black}scp -r jquery-webpack-stats.json fzy@174.138.16.121:/home/fzy/workplace/koe/${Color_Off}"
    scp -r jquery-webpack-stats.json fzy@174.138.16.121:/home/fzy/workplace/koe/
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Green}${On_Black}scp -r webpack-stats.json fzy@174.138.16.121:/home/fzy/workplace/koe/${Color_Off}"
    scp -r webpack-stats.json fzy@174.138.16.121:/home/fzy/workplace/koe/
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Yellow}${On_Purple}Now, run gunicorn remotely ${Color_Off}"
    echo -e "${Green}${On_Black}ssh fzy@174.138.16.121 \"/home/fzy/workplace/koe/post-deploy.sh\"${Color_Off}"
    ssh fzy@174.138.16.121 "/home/fzy/workplace/koe/post-deploy.sh"
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Yellow}${On_Purple}Now, remove the compiled bundles, rebuild the production version (no compile)${Color_Off}"
    echo -e "${Green}${On_Black}rm -rf assets/bundles${Color_Off}"
    rm -rf assets/bundles
    echo -e "${Green}${On_Black}yarn build${Color_Off}"
    yarn build
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Black}${On_Green}ALL DONE${Color_Off}"
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi
