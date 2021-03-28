# Installation checklist:
    * [ ] Install C++ compiler
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

## Install C++ compiler
Don't use brew's GCC to compile koe - it can be done BUT you the process involves setting a million of compiler flags 
and even if you succeed in compiling it, Koe might still not run due to linkage errors. Don't waste your time. 
Just use CLang, which is included in XCode. So you just need to install XCode. 

## Install python 3.9
Download a binary package from here and follow the instruction: https://www.python.org/downloads/mac-osx/

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

## Install MySQL
Koe was initially set up to work on MySQL, SQLite and Postgres, however the database
and especially the queries have become quite complicated over time, and now it no longer works
on PostGres (although with some extra work I can make it work on PostGres again - I'm just lazy)

SQLite is very simple to set up so I'm not addressing that here. If you wish to use MySQL then follow
this instruction

The version that guarantees to work is MySQL 5.7. If you already have a newer version then feel free to try
```bash
brew install mysql@5.7
mysql.server start
```

## Install Redis (optional)
Redis is used as a caching service. For development this is not required.
```bash
brew install redis
brew services start redis
```

## Install python packages
```bash
pip install -r requirements-conda-forge.txt
```

## Modify settings.yaml
Before running the app you must provide a customised settings.yaml file (located inside `settings/` folder)
Just open `settings.yaml` and replace `yourname` etc... with the appropriate values 

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

You can install node@10 using brew, but downloading the binary executable from their website is way easier and less messy 
https://nodejs.org/dist/latest-v10.x/

Extract the content somewhere, and change the PATH variable to include node's `bin` folder.

### Install node libraries
```bash
npm install yarn
yarn install
```
