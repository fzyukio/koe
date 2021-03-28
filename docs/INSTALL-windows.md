> WARNING: Installing Koe on Windows is MUCH more difficult than on Mac/Linux

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
Install Microsoft Build Tools 2015: go to https://www.visualstudio.com/vs/older-downloads/.
Then go to Redistributables and Build Tools. Download "Microsoft Build Tools 2015 Update 3"
Check that the file you download is named "visualcppbuildtools_full.exe"

## Install python 3.6
Download a binary package from here and follow the instruction: https://www.python.org/downloads/windows/
Recommend installing to `C:\Python36`. On Windows, you might have to manually add the path to python (`C:\Python36` and `C:\Python36\Scripts`) to the environment variable `PATH`.

## Install virtualenv
Open a CMD window and type:
```cmd
pip install virtualenv
```

### Create a virtual environment:
> Note: if you use PyCharm, make sure you run this command BEFORE importing the project into Pycharm. Otherwise it will use the default interpreter and you'll have to change that

```bash
virtualenv .venv
```

### Activate the virtual environment.
> Note: You only need to do this when you run commands from a CMD window. On Pycharm, the virtualenv is automatically loaded.

#### Using command line (`cmd`)
```shell
.venv\Scripts\activate.bat
```
#### Using POSIX terminal e.g. git bash, cygwin, Mingw
```bash
source .venv/Scripts/activate
```

## Install MySQL
Koe was initially set up to work on MySQL, SQLite and Postgres, however the database
and especially the queries have become quite complicated over time, and now it no longer works
on PostGres (although with some extra work I can make it work on PostGres again - I'm just lazy)

SQLite is very simple to set up so I'm not addressing that here. If you wish to use MySQL then follow
this instruction

The version that guarantees to work is MySQL 5.7. If you already have a newer version then feel free to try
Download the installer here and follow its instruction: https://dev.mysql.com/downloads/windows/installer/5.7.html


## Install Redis (optional)
Redis is used as a caching service. For development this is not required. Redis does not officially support Windows. However it is possible to install a "moderately out-dated" version of Redis on Windows
Follow instruction here: https://redislabs.com/ebook/appendix-a/a-3-installing-on-windows/a-3-2-installing-redis-on-window/

## Install python packages
```bash
pip install -r requirements.txt
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

Download the binary from here https://nodejs.org/dist/latest-v10.x/
Extract the content somewhere, and change the PATH variable to include node's `bin` folder.

### Install node libraries
```bash
npm install yarn
yarn install
```
