"""
This script will create all necessary stuff for the app to work.

Including: - Generating a settings.yaml file with a random SECRET_KEY if this file does not exist,
           - Reset, backup, restore the database to fixtures or to sql dump
"""
import os
import uuid

import time
from contextlib import contextmanager

import collections
import yaml
import zipfile
from shutil import copyfile

from django.core.files.temp import NamedTemporaryFile

fixture_list = [
    'root.user',
    'root.extraattr',
    'root.columnactionvalue',
    'cms',
    'koe.database',
    'koe.accessrequest',
    'koe.databaseassignment',
    'koe.historyentry',
    'koe.distancematrix',
    'koe.coordinate',
    'koe.species',
    'koe.individual',
    'koe.audiotrack',
    'koe.audiofile',
    'koe.segment',
    'koe.invitationcode',
    'root.extraattrvalue',
]


CONF = {}


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

    if len(CONF) > 0:
        return CONF

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
    CONF.update(conf)

    return CONF


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


@contextmanager
def create_tmp_mysql_conf():
    """
    Make a temporary file to store password for secure MySQL login
    :return:
    """
    with NamedTemporaryFile(mode='w+', delete=True) as f:
        f.write('[client]')
        f.write('\n')
        f.write('password=')
        f.write(db_pass)
        f.write('\n')
        f.write('user=')
        f.write(db_user)
        f.write('\n')
        f.write('host=')
        f.write(db_host)
        f.write('\n')
        f.write('port=')
        f.write(str(db_port))
        f.write('\n')
        f.write('\n')
        f.flush()

        yield f


def reset_mysql():
    """
    Reset Mysql database to empty.

    :return: None
    """
    with create_tmp_mysql_conf() as temp_conf:
        # generic command to log in mysql
        cmd = ['mysql', '--defaults-extra-file={}'.format(temp_conf.name), '--database', db_name]

        # Run query 'show tables;' and get the result
        result, err = run_command(cmd + ['-e', 'show tables;'], suppress_output=True)

        result_lines = result.decode('utf-8').split('\n')

        # From the result construct a series of queries to drop the tables
        drop_table_queries = ['SET FOREIGN_KEY_CHECKS = 0;']
        for line in result_lines:
            line = line.strip()
            if line and not line.startswith('Tables_in'):
                drop_table_queries.append('DROP TABLE IF EXISTS {};'.format(line))

        # Now run those drop table queries
        run_command(cmd + ['-e', ''.join(drop_table_queries)])
        return err == b''


def backup_mysql():
    """
    Reset Mysql database to empty.

    :param filename: path to the backup file. If exists it will be overwritten
    :return: None
    """
    with create_tmp_mysql_conf() as temp_conf:
        cmd = ['mysqldump', '--defaults-extra-file={}'.format(temp_conf.name), db_name, '--result-file', backup_file]
        out, err = run_command(cmd, suppress_output=True)

        return err == b''


def restore_mysql():
    """
    Reset Mysql database to empty.

    :return: None
    """
    with create_tmp_mysql_conf() as temp_conf:
        # generic command to log in mysql
        cmd = [
            'mysql',
            '--defaults-extra-file={}'.format(temp_conf.name),
            '--init-command', 'SET FOREIGN_KEY_CHECKS=0;',
            '--database', db_name
        ]
        out, err = run_command(cmd + ['--execute', 'source {}'.format(backup_file)], suppress_output=True)

        return err == b''


def backup_sqlite():
    """
    Remove the sqlite3 data file.

    :return:
    """
    try:
        copyfile(db_name, backup_file)
        return True
    except FileNotFoundError:
        talk_to_user('File {} not found - no backup created.'.format(db_name))
        return False


def restore_sqlite():
    """
    Restore the sqlite3 data file - simply by copying the backup over

    :return:
    """
    try:
        copyfile(backup_file, db_name)
        return True
    except FileNotFoundError:
        talk_to_user('File {} not found - no backup created.'.format(db_name))
        return False


def reset_sqlite():
    """
    Remove the sqlite3 data file.

    :return:
    """
    db_name = db_config['NAME']
    try:
        os.remove(db_name)
    except FileNotFoundError:
        # Not a problem if file doesn't exist
        pass

    return True


@contextmanager
def create_tmp_postgre_conf():
    """
    Postgres doesn't accept password from command line, so we have to create a temporary .pgpass file.
    :return:
    """
    if db_pass:
        from django.db.backends.postgresql.client import _escape_pgpass
        with NamedTemporaryFile(mode='w+', delete=True) as temp_pgpass:
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

            yield temp_pgpass
    else:
        yield


def reset_postgres():
    """
    Reset Postgres database to empty.

    :return: None
    """
    # generic command to log in postgres
    cmd = [
        'psql',
        '--username', db_user,
        '--host', db_host,
        '--port', str(db_port),
        '--dbname', db_name
    ]

    with create_tmp_postgre_conf():
        # Now run query DROP SCHEMA public CASCADE; CREATE SCHEMA public; to empty the database
        out, err = run_command(cmd + ['-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'], suppress_output=True)
        return err != b''


def backup_postgres():
    """
    Make a dump from Postgres database

    :param filename: path to the backup file. If exists it will be overwritten
    :return: None
    """
    cmd = [
        'pg_dump',
        '--username', db_user,
        '--host', db_host,
        '--port', str(db_port),
        '--dbname', db_name,
        '--file', backup_file,
        '--format', 'plain'
    ]

    with create_tmp_postgre_conf():
        message, err = run_command(cmd, suppress_output=True)

    talk_to_user(message.decode('utf-8'))
    return err != b''


def restore_postgres():
    """
    Reset Postgres database to empty.

    :param filename: path to the backup file. If exists it will be overwritten
    :return: None
    """
    cmd = [
        'psql',
        '--username', db_user,
        '--host', db_host,
        '--port', str(db_port),
        '--dbname', db_name,
        '--file', backup_file
    ]

    with create_tmp_postgre_conf():
        message, err = run_command(cmd, suppress_output=True)

    talk_to_user(message.decode('utf-8'))
    return True


def run_command(cmd, suppress_output=False, suppress_error=False):
    """
    Run python manage command.

    :param cmd: an array of arguments, or a complete command.
    :param suppress_output: if True, don't print output to screen
    :parem suppress_error: if True, don't print error to screen
    :return: out
    """
    import sys
    import subprocess

    if isinstance(cmd, str):
        cmd = cmd.split(' ')

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out_lines = []
    err_lines = []

    while True:
        out_byte = p.stdout.readline()
        err_byte = p.stderr.readline()
        if out_byte == err_byte == b'' and p.poll() is not None:
            break
        else:
            out_line_str = out_byte.decode()
            out_lines.append(out_line_str)

            err_line_str = err_byte.decode()
            err_lines.append(err_line_str)

            if not suppress_output:
                sys.stdout.write(out_line_str)
                sys.stdout.flush()

            if not suppress_error:
                sys.stderr.write(err_line_str)
                sys.stderr.flush()

    out = ''.join(out_lines).encode()
    err = ''.join(err_lines).encode()

    return out, err


def run_loaddata(fixture_dir, fixture_name):
    """
    Import fixtures.

    :param fixture_dir: directory of the fixtures
    :param fixture_name: name of the fixtures (django qualified name)
    :return:
    """
    fixture_file = os.path.join(fixture_dir, '{}.json'.format(fixture_name))
    talk_to_user('Loading {} from {}'.format(fixture_name, fixture_file))
    command = 'python manage.py loaddata {}'.format(fixture_file)
    run_command(command)


def run_dumpdata(fixture_dir, fixture_name):
    """
    Export fixtures.

    :param fixture_dir: directory of the fixtures
    :param fixture_name: name of the fixtures (django qualified name)
    :return:
    """
    fixture_file = os.path.join(fixture_dir, '{}.json'.format(fixture_name))
    talk_to_user('Dumping {} to {}'.format(fixture_name, fixture_file))
    command = 'python manage.py dumpdata {} --natural-foreign --indent=2'.format(fixture_name)
    out, err = run_command(command, suppress_output=True)

    print(out.decode('utf-8'))

    with open(fixture_file, 'wb') as f:
        f.write(out)


def run_compress_fixtures(fixture_dir, compressed_file_name):
    with zipfile.ZipFile(compressed_file_name, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
        for fixture_name in fixture_list:
            fixture_file = os.path.join(fixture_dir, '{}.json'.format(fixture_name))
            with open(fixture_file, 'r') as f:
                zip_file.writestr('{}.json'.format(fixture_name), f.read())


def probe_sqlite():
    """
    Sqlite is always available

    :return: None
    """
    return True


def probe_postgres():
    cmd = [
        'psql',
        '--username', db_user,
        '--host', db_host,
        '--port', str(db_port),
        '--dbname', db_name,
    ]

    message, err = run_command(cmd, suppress_output=True, suppress_error=True)

    err = err.decode('utf-8').strip().split('\n')
    error_messages = [x for x in err if x.find('Connection refused') != -1 or x.find('FATAL') != -1]
    return len(error_messages) == 0


def probe_mysql():
    """
    Reset Mysql database to empty.

    :param filename: path to the backup file. If exists it will be overwritten
    :return: None
    """
    with create_tmp_mysql_conf() as temp_conf:
        # generic command to log in mysql
        cmd = [
            'mysql', '--defaults-extra-file={}'.format(temp_conf.name),
            '--database', db_name, '--execute', 'show tables;'
        ]
        out, err = run_command(cmd, suppress_output=True, suppress_error=True)
        err = err.decode('utf-8').strip().split('\n')
        error_messages = [x for x in err if x.startswith('ERROR')]
        return len(error_messages) == 0


reset_db_functions = {
    'sqlite3': reset_sqlite,
    'postgresql': reset_postgres,
    'mysql': reset_mysql
}

restore_db_functions = {
    'sqlite3': restore_sqlite,
    'postgresql': restore_postgres,
    'mysql': restore_mysql
}

backup_db_functions = {
    'sqlite3': backup_sqlite,
    'postgresql': backup_postgres,
    'mysql': backup_mysql
}

probe_db_functions = {
    'sqlite3': probe_sqlite,
    'postgresql': probe_postgres,
    'mysql': probe_mysql
}


def wait_for_database():
    talk_to_user('Testing database connection...')
    probe_db_function = probe_db_functions[db_engine_short_name]

    connectable = probe_db_function()
    while not connectable:
        connectable = probe_db_function()
        print('Connection is not ready, sleep for 1 sec')
        time.sleep(1)

    return True


def empty_database():
    talk_to_user('Resetting database to empty...')
    reset_db_function = reset_db_functions[db_engine_short_name]
    return reset_db_function()


def apply_migrations():
    talk_to_user('Apply migration...')
    out, err = run_command('python manage.py makemigrations koe')
    if err == b'':
        out, err = run_command('python manage.py makemigrations root')

    if err == b'':
        out, err = run_command('python manage.py migrate --database=default')

    return err == b''


def backup_database_using_fixtures():
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
        for fixture_name in fixture_list:
            talk_to_user('Dumping {} to {}'.format(fixture_name, backup_file))
            command = 'python manage.py dumpdata {} --natural-foreign --indent=2'.format(fixture_name)
            out, err = run_command(command, suppress_output=True)
            zip_file.writestr(fixture_name, out.decode('utf-8'))

    return True


def backup_database_using_sql():
    talk_to_user('Backing up database...'.format(db_engine))

    backup_db_function = backup_db_functions[db_engine_short_name]
    success = backup_db_function()

    if success:
        talk_to_user('Successfully backed up database to {}'.format(backup_file))

    return success


def restore_database_using_fixtures():
    talk_to_user('Importing fixtures from {}'.format(backup_file))

    with zipfile.ZipFile(backup_file, 'r') as zip_file:
        namelist = zip_file.namelist()
        for fixture_name in fixture_list:
            if fixture_name not in namelist:
                continue

            fixture_content = zip_file.read(fixture_name)

            temp_file_name = '/tmp/{}.json'.format(uuid.uuid4().hex)
            with open(temp_file_name, 'wb') as f:
                f.write(fixture_content)

            talk_to_user('Loading {}'.format(fixture_name))
            command = 'python manage.py loaddata {}'.format(temp_file_name)
            run_command(command)

            os.remove(temp_file_name)
    return True


def restore_database_using_sql():
    talk_to_user('Restoring database from {}'.format(backup_file))
    restore_db_function = restore_db_functions[db_engine_short_name]
    success = restore_db_function()

    if success:
        talk_to_user('Successfully restored database')

    return success


def handle_function(func: collections.Callable, *args, **kwargs):
    func_name = func.__name__
    start = time.time()

    no_error = func(*args, **kwargs)

    end = time.time()
    talk_to_user('{0:s}: finished in {1: 9.9f} seconds'.format(func_name, end - start))

    if not no_error:
        talk_to_user('Terminated due to an error')
        exit(1)


if __name__ == '__main__':
    import argparse
    from colorama import Fore, Back, Style, init as colorama_init
    import dj_database_url

    colorama_init()
    parser = argparse.ArgumentParser()

    parser.add_argument('--probe-database', dest='wait_db', action='store_true', default=False,
                        help='Try to connect to db until it is connectable')

    parser.add_argument('--reset-database', dest='reset_db', action='store_true', default=False,
                        help='Truncate all tables. Database structure restored')

    parser.add_argument('--empty-database', dest='empty_db', action='store_true', default=False,
                        help='Truncate all tables. Database will be completely empty')

    parser.add_argument('--restore-database', dest='restore_db', action='store_true', default=False,
                        help='Empty the database, then restore it with fixtures or sql dump')
    parser.add_argument('--backup-database', dest='backup_db', action='store_true', default=False,
                        help='Dump current data to fixtures or sql dump')

    parser.add_argument('--file', dest='backup_file', action='store',
                        help='path to the file to restore from or backup to.')

    parser.add_argument('--generate-config', dest='generate_config', action='store_true', default=False,
                        help='path to the file to restore from or backup to.')

    args = parser.parse_args()
    reset_db = args.reset_db
    restore_db = args.restore_db
    backup_db = args.backup_db
    backup_file = args.backup_file
    empty_db = args.empty_db
    wait_db = args.wait_db
    generate_config = args.generate_config
    config = get_config()

    if generate_config:
        populate_environment_variables(config)

    if restore_db and backup_db:
        raise Exception('Cannot use both params --restore-database and --backup-database')

    if restore_db:
        if not backup_file:
            raise Exception('To restore data, parameter --file is required')
        if not os.path.isfile(backup_file):
            raise Exception('File {} doesn\'t exist'.format(backup_file))

    if backup_db:
        if not backup_file:
            raise Exception('To backup data, parameter --file is required')

    db_config = dj_database_url.parse(config['database_url'])
    db_engine = db_config['ENGINE']
    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_pass = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config['PORT']

    if db_engine == 'django.db.backends.sqlite3':
        db_engine_short_name = 'sqlite3'
    elif db_engine.startswith('django.db.backends.postgresql'):
        db_engine_short_name = 'postgresql'
    elif db_engine == 'django.db.backends.mysql':
        db_engine_short_name = 'mysql'
    else:
        raise Exception('Database engine {} is not supported.'.format(db_engine))

    if wait_db:
        handle_function(wait_for_database)

    if backup_db:
        if backup_file.endswith('.zip'):
            handle_function(backup_database_using_fixtures)
        else:
            handle_function(backup_database_using_sql)

    os.environ['IMPORTING_FIXTURE'] = 'true'

    if reset_db or empty_db:
        handle_function(empty_database)

    if reset_db:
        handle_function(apply_migrations)

    if restore_db:
        handle_function(empty_database)
        if backup_file.endswith('.zip'):
            handle_function(restore_database_using_fixtures)
        else:
            handle_function(restore_database_using_sql)

        handle_function(apply_migrations)

    del os.environ['IMPORTING_FIXTURE']

    talk_to_user('All done!')
