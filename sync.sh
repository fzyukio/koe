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

BACKUP_NAME=backup-`date "+%Y-%m-%d_%H-%M-%S"`.sql
DOCKER_NAME=koe_app

SOURCE=$1
TARGET=$2

if [[ -z "$SOURCE" ]]; then
    echo "Usage: sync.sh source_cfg_file target_cfg_file"
    exit 0
fi

if [[ "$SOURCE" != "this" && ! -f ${SOURCE} ]]; then
    echo "File $SOURCE not found!"
    exit 1
fi

if [[ -z "$TARGET" ]]; then
    echo "Usage: sync.sh source_cfg_file target_cfg_file"
    exit 0
fi

if [[ "$TARGET" != "this" ]]; then
    if [[ ! -f ${TARGET} ]]; then
        echo "File $TARGET not found!"
        exit 1
    fi
fi

if [[ "$SOURCE" = "$TARGET" ]]; then
    echo "Source and Target cannot be the same"
    exit 1
fi

if [[ "$SOURCE" != "this" ]]; then
    source $SOURCE
    echo -e "${Yellow}${On_Purple}Create a backup on the remote machine${Color_Off}"
    echo -e "${Green}${On_Black}docker exec -it koe_app python maintenance.py --backup-database --file=backups/mysql/$BACKUP_NAME${Color_Off}"
    ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "cd $WORKSPACE; docker exec koe_app python maintenance.py --backup-database --file=backups/mysql/$BACKUP_NAME"

    echo -e "${Yellow}${On_Purple}Copy it over here${Color_Off}"
    echo -e "${Green}${On_Black}scp $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/backups/mysql/$BACKUP_NAME $BACKUP_NAME${Color_Off}"
    scp $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/backups/mysql/$BACKUP_NAME backups/mysql/$BACKUP_NAME
    ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "cd $WORKSPACE; rm -f backups/mysql/$BACKUP_NAME"
else
    source .venv/bin/activate
#    echo -e "${Yellow}${On_Purple}Create a backup on the local machine${Color_Off}"
#    echo -e "${Green}${On_Black}python maintenance.py --backup-database --file=backups/mysql/$BACKUP_NAME${Color_Off}"
#    python maintenance.py --backup-database --file=backups/mysql/$BACKUP_NAME
fi

# if the target is this, copy remote file back here
# Otherwise, if the source is this, copy local files to the remote server
if [[ "$TARGET" = "this" ]]; then
    source ./.venv/bin/activate
    echo -e "${Yellow}${On_Purple}Restore the backup in the local machine${Color_Off}"
    echo -e "${Green}${On_Black}python maintenance.py --restore-database --file=backups/mysql/$BACKUP_NAME${Color_Off}"
    python maintenance.py --restore-database --file=backups/mysql/$BACKUP_NAME
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/ordination user_data/${Color_Off}"
    rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/ordination user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/similarity user_data/${Color_Off}"
    rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/similarity user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/measurement user_data/${Color_Off}"
    rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/measurement user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/audio user_data/${Color_Off}"
    rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/audio user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/pickle user_data/${Color_Off}"
    rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/pickle user_data/
else
    source ${TARGET}
#    echo -e "${Yellow}${On_Purple}Copy it to the target${Color_Off}"
#    echo -e "cp $SSH_EXTRA_CREDENTIAL backups/mysql/$BACKUP_NAME $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/backups/mysql/$BACKUP_NAME"
#    scp ${SSH_EXTRA_CREDENTIAL} backups/mysql/${BACKUP_NAME} ${REMOTE_USER}@${REMOTE_ADDRESS}:${WORKSPACE}/backups/mysql/$BACKUP_NAME
#
#    echo -e "${Yellow}${On_Purple}Restore the backup in remote machine${Color_Off}"
#    echo -e "${Green}${On_Black}docker exec -it koe_app python maintenance.py --restore-database --file=backups/mysql/$BACKUP_NAME${Color_Off}"
#    ssh $SSH_EXTRA_CREDENTIAL $REMOTE_USER@$REMOTE_ADDRESS "cd $WORKSPACE; docker exec koe_app python maintenance.py --restore-database --file=backups/mysql/$BACKUP_NAME"
fi

if [[ "$SOURCE" = "this" ]]; then
    source ${TARGET}
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/ordination user_data/${Color_Off}"
    rsync -aP user_data/ordination $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/similarity user_data/${Color_Off}"
    rsync -aP user_data/similarity $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/measurement user_data/${Color_Off}"
    rsync -aP user_data/measurement $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/audio user_data/${Color_Off}"
    rsync -aP user_data/audio $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/
    echo -e "${Green}${On_Black}rsync -aP $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/pickle user_data/${Color_Off}"
    rsync -aP user_data/pickle $REMOTE_USER@$REMOTE_ADDRESS:$WORKSPACE/user_data/
fi
