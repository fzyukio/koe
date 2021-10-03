# Installation checklist:
    * [ ] Install conda-forge
    * [ ] Install MySQL
    * [ ] Install Redis (optional)
    * [ ] Install Python packages
    * [ ] Modify settings.yaml
    * [ ] Initialise the database
    * [ ] Install NodeJS
    * [ ] Install node libraries

# Installation details:
## Install Conda-forge
```
brew install --cask miniforge

# Create new environment
conda create --name py39 python=3.9

# Activate the new environment
conda activate py39

# Install the following packages:
conda install -y numpy==1.20.1
conda install -y scikit-image==0.18.1
conda install -y scikit-learn==0.24.0
conda install -y scipy==1.6.1
conda install -y matplotlib==3.3.4
conda install -y pillow==8.1.2
conda install -y llvmlite==0.36.0
conda install -y numba==0.53.0
conda install -y libsndfile==1.0.31
conda install -y mysqlclient==1.4.2.post1
```

## Install MySQL (both conda and non-conda)
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

It is not possible to install node@10 by conda-forge, and any attempt to compile from source will
likely result in compilation error. So don't try.

Instead, download the binary from here https://nodejs.org/dist/latest-v10.x/

Extract the content somewhere, and change the PATH variable to include node's `bin` folder.

### Install node libraries
```bash
npm install yarn
yarn install
```
