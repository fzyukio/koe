"""
This script will create all necessary stuff for the app to work.

Including: - Generating a settings.yaml file with a random SECRET_KEY if this file does not exist,
           - Reset the database
           - Populate the database with fixtures
"""

import os
import yaml


__all__ = ['config']


def get_config():
    """
    If file 'settings.yaml' doesn't exist, create one from template, otherwise read it.

    If the file is created, also generate and append the secret key to the end of it.
    :return: the config dictionary
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(base_dir, 'settings.yaml')
    default_filename = os.path.join(base_dir, 'settings.default.yaml')

    if not os.path.isfile(filename):
        raise Exception('File {} not found, please make a copy of {}'.format(filename, default_filename))

    with open(filename, 'r', encoding='utf-8') as f:
        conf = yaml.load(f)

    if conf.get('secret_key', None) is None:
        import random
        import string
        with open(filename, 'a', encoding='utf-8') as f:
            # Generate a random key
            secret = ''.join([random.SystemRandom().choice(
                '{}{}'.format(string.ascii_letters, string.digits)) for _ in range(50)])
            f.write('secret_key: r\'{}\''.format(secret))

    with open(filename, 'r', encoding='utf-8') as f:
        conf = yaml.load(f)

    conf['base_dir'] = base_dir
    return conf


def populate_environment_variables(config):
    """
    Populate the environment with all the pairs of key-value under 'environment_variables'.

    :param config: the config dictionary
    :return: None
    """
    if 'environment_variables' in config:
        vars = config['environment_variables']
        for name, value in vars.items():
            os.environ[name] = str(value)


def talk_to_user(message):
    """
    Print message to user of a special formatted way, to distinguish it from command output.

    :param message: the message
    :return: None
    """
    print(Back.BLUE + Fore.WHITE + message + Style.RESET_ALL)


def reset_mysql(db_config):
    """
    Reset Mysql database to empty.

    :param db_config: the dj_database_url object
    :return: None
    """
    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_pass = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config['PORT']

    # generic command to log in mysql
    cmd = ['mysql',
           '--user={}'.format(db_user),
           '--password={}'.format(db_pass),
           '--host={}'.format(db_host),
           '--port={}'.format(db_port),
           '--database={}'.format(db_name)
           ]

    # Run query "show tables;" and get the result
    result = run_command(cmd + ['-e', 'show tables;'], suppress_output=True)

    result_lines = result.decode('utf-8').split('\n')

    # From the result construct a series of queries to drop the tables
    drop_table_queries = ['SET FOREIGN_KEY_CHECKS = 0;']
    for line in result_lines:
        line = line.strip()
        if line and not line.startswith('Tables_in'):
            drop_table_queries.append('DROP TABLE IF EXISTS {};'.format(line))

    # Now run those drop table queries
    run_command(cmd + ['-e', ''.join(drop_table_queries)])


def reset_sqlite(db_config):
    """
    Remove the sqlite3 data file.

    :param db_config: the dj_database_url object
    :return:
    """
    db_name = db_config['NAME']
    try:
        os.remove(db_name)
    except FileNotFoundError:
        # Not a problem if file doesn't exist
        pass


def reset_postgres(db_config):
    """
    Reset Postgres database to empty.

    :param db_config: the dj_database_url object
    :return: None
    """
    from django.core.files.temp import NamedTemporaryFile
    from django.db.backends.postgresql.client import _escape_pgpass

    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_pass = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config['PORT']

    # generic command to log in postgres
    cmd = ['psql',
           '--username={}'.format(db_user),
           '--host={}'.format(db_host),
           '--port={}'.format(db_port),
           '--dbname={}'.format(db_name)]

    if db_pass:
        # Postgres doesn't accept password from command line, so we have to create a temporary .pgpass file.
        temp_pgpass = NamedTemporaryFile(mode='w+')
        print(
            _escape_pgpass(db_host) or '*',
            str(db_port) or '*',
            _escape_pgpass(db_name) or '*',
            _escape_pgpass(db_user) or '*',
            _escape_pgpass(db_pass),
            file=temp_pgpass,
            sep=':',
            flush=True,
        )
        os.environ['PGPASSFILE'] = temp_pgpass.name

    # Now run query DROP SCHEMA public CASCADE; CREATE SCHEMA public; to empty the database
    run_command(cmd + ['-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'], suppress_output=True)


def run_command(cmd, suppress_output=False):
    """
    Run python manage command.

    :param cmd: an array of arguments, or a complete command.
    :param suppress_output: if True, don't print to screen
    :return: out
    """
    import sys
    import subprocess

    if isinstance(cmd, str):
        cmd = cmd.split(' ')

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if not suppress_output:
        if out:
            print(out.decode('utf-8'), end='', flush=True)
    if err:
        print(err.decode('utf-8'), file=sys.stderr, end='', flush=True)

    return out


def run_loaddata(fixture):
    """
    Import fixtures.

    :param fixture: path to the fixture (JSON) file
    :return:
    """
    command = 'python manage.py loaddata {}'.format(fixture)
    run_command(command)


config = get_config()
populate_environment_variables(config)


def base_dir_join(*args):
    return os.path.join(config['base_dir'], *args)


if __name__ == '__main__':
    import argparse
    from colorama import Fore, Back, Style, init as colorama_init
    import dj_database_url

    parser = argparse.ArgumentParser()
    parser.add_argument('--clear-database', dest='clear_db', action='store_true', default=False)
    args = parser.parse_args()
    clear_db = args.clear_db

    if clear_db:
        colorama_init()

        db_config = dj_database_url.parse(config['database_url'])
        db_engine = db_config['ENGINE']

        talk_to_user('You are using database engine: {}. I\'m resetting it to empty...'.format(db_engine))

        if db_engine == 'django.db.backends.sqlite3':
            reset_sqlite(db_config)
        elif db_engine.startswith('django.db.backends.postgresql'):
            reset_postgres(db_config)
        elif db_engine == 'django.db.backends.mysql':
            reset_mysql(db_config)

        os.environ['IMPORTING_FIXTURE'] = 'true'

        talk_to_user('Now I\'m recreating all the tables')
        run_command('python manage.py makemigrations koe')
        run_command('python manage.py makemigrations root')
        run_command('python manage.py migrate --database=default')

        talk_to_user('Now I\'m importing some fixtures')
        run_loaddata('koe/fixtures/users.json')
        run_loaddata('koe/fixtures/cms.json')
        run_loaddata('koe/fixtures/data.json')
        run_loaddata('koe/fixtures/root.columnactionvalue.json')
        run_loaddata('koe/fixtures/root.extraattr.json')
        run_loaddata('koe/fixtures/root.extraattrvalue.json')

        os.environ['IMPORTING_FIXTURE'] = 'false'

        talk_to_user('All done!')
