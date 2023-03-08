# Installation checklist:
    * [ ] Install python 3.9
    * [ ] Install virtualenv
    * [ ] Set up an environment
    * [ ] Install MySQL
    * [ ] Install Redis (optional)
    * [ ] Install Python packages
    * [ ] Modify settings.yaml
    * [ ] Initialise the database
    * [ ] Install NodeJS
    * [ ] Install node libraries

# Installation details:

## Install python 3.9
You can install python 3.9 with apt/yum, but it's probably a lot easier to just download a binary package from here and follow the instruction: https://www.python.org/downloads/source/

## Install virtualenv
Open a terminal or cmd window and type:
```bash
pip install virtualenv
```

## Set up an environment
### Create a virtual environment:
> Note: if you use PyCharm, make sure you run this command BEFORE importing the project into Pycharm. Otherwise it will use the default interpreter and you'll have to change that

```bash
virtualenv .venv
```

### Activate the virtual environment.
> Note: You only need to do this when you run commands from the terminal. On Pycharm, the virtualenv is automatically loaded.

```bash
source .venv/bin/activate
```

## Install MySQL (both conda and non-conda)
Koe was initially set up to work on MySQL, SQLite and Postgres, however the database
and especially the queries have become quite complicated over time, and now it no longer works
on PostGres (although with some extra work I can make it work on PostGres again - I'm just lazy)

SQLite is very simple to set up so I'm not addressing that here. If you wish to use MySQL then follow
this instruction

The version that guarantees to work is MySQL 5.7. If you already have a newer version then feel free to try

Follow the instruction here: https://www.howtoforge.com/tutorial/how-to-install-mysql-57-on-linux-centos-and-ubuntu/

## Install Redis (optional)
Redis is used as a caching service. For development this is not required.
Follow instruction here: https://redis.io/download


## Install python packages
```bash
pip install -r requirements.txt
```

## Modify settings.yaml
Before running the app you must provide a customised settings.yaml file (located inside `settings/` folder)
Just open `settings.yaml` and replace `yourname` etc... with the appropriate values 

### Create a new database
Assuming you have mysql installed, login to the database as root and create a database named `koe`, a user named `koe` and password `koe`. Of course you can choose different names/values of these, but you will need to change the corresponding variable in `settings.yaml`

## Initialise the database:
```bash
python maintenance.py --restore-database --file=initial.zip
# Then you need to reset the superuser's password with:
python manage.py changepassword superuser
```

## Install NodeJS
The only version that can run this app is Node 10, if you have another version installed,
you must still install node 10 and set the appropriate PATH such that when inside Koe, the following command

```bash
node -v
```

Should yield `v10.xx.xx`

You can install node@10 using apt/yum, but downloading the binary executable from their website is way easier and less messy 
https://nodejs.org/dist/latest-v10.x/

Extract the content somewhere, and change the PATH variable to include node's `bin` folder.

### Install node libraries
```bash
npm install yarn
yarn install
```
