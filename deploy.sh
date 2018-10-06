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

PACKAGE_NAME=package-`date "+%Y-%m-%d_%H-%M-%S"`.tar.gz
APP_NAME=koe

CFG_FILE=$1

if [ -z "$CFG_FILE" ]; then
    echo "Usage: deploy.sh deploy-config-file"
    exit 0
fi

if [ ! -f $CFG_FILE ]; then
    echo "File $CFG_FILE not found!"
    exit 1
fi

source $CFG_FILE
source ./.venv/bin/activate

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
    echo -e "${Green}${On_Black}tar -cvf $PACKAGE_NAME assets/bundles static jquery-webpack-stats.json webpack-stats.json${Color_Off}"
    tar -cvf $PACKAGE_NAME assets/bundles static jquery-webpack-stats.json webpack-stats.json
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

RESULT=$?
if [ $RESULT -eq 0 ]; then

    echo -e "${Yellow}${On_Purple}Now copying the package${Color_Off}"
    echo -e "${Green}${On_Black}scp $SSH_EXTRA_CREDENTIAL $PACKAGE_NAME $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/${Color_Off}"
    scp $SSH_EXTRA_CREDENTIAL $PACKAGE_NAME $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

echo -e "${Yellow}${On_Purple}Remove all old assets from the remote site${Color_Off}"
echo -e "${Green}${On_Black}ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS \"rm -rf $WORKSPACE/assets/bundles $WORKSPACE/static\"${Color_Off}"
ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "rm -rf $WORKSPACE/assets/bundles $WORKSPACE/static"

echo -e "${Yellow}${On_Purple}Make sure the server's code is up-to-date${Color_Off}"
echo -e "${Green}${On_Black}ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS \"cd $WORKSPACE; git pull\"${Color_Off}"
ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "cd $WORKSPACE; git pull"

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${Yellow}${On_Purple}Now extracting the package${Color_Off}"
    echo -e "${Green}${On_Black}tar --warning=no-unknown-keyword -xvf $PACKAGE_NAME${Color_Off}"
    ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "cd $WORKSPACE;tar --warning=no-unknown-keyword -xvf $PACKAGE_NAME"
else
    echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
    exit
fi

# RESULT=$?
# if [ $RESULT -eq 0 ]; then
#     echo -e "${Yellow}${On_Purple}Now, run the app remotely ${Color_Off}"
#     echo -e "${Green}${On_Black}ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS \"source ~/.profile $WORKSPACE/post-deploy.sh\"${Color_Off}"
#     ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "source ~/.profile; $WORKSPACE/post-deploy.sh"
# else
#     echo -e "${White}${On_Red}FAILED!!!! Exit.${Color_Off}"
#     exit
# fi

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

ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "rm $WORKSPACE/$PACKAGE_NAME"
rm $PACKAGE_NAME
