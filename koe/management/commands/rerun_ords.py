import os
from logging import warning

from koe.feature_utils import _construct_ordination
from koe.management.abstract_commands.recreate_persisted_objects import RecreateIdsPersistentObjects
from koe.models import Ordination
from koe.task import ConsoleTaskRunner


class Command(RecreateIdsPersistentObjects):
    def perform_action(self, when, remove_dead):
        ords = Ordination.objects.all()
        for ord in ords:
            need_reconstruct = self.check_rebuild_necessary(ord, when)

            if need_reconstruct:
                dead = True
                try:
                    print('==============================================')
                    runner = ConsoleTaskRunner(prefix='Reconstruct ordination {}'.format(ord))
                    _construct_ordination(ord, runner)
                    runner.complete()
                    dead = False
                except AssertionError as e:
                    errmsg = str(e)
                    if errmsg.startswith('Unknown method mds'):
                        warning('Unrecoverable error: ' + errmsg)
                    else:
                        raise
                except ValueError as e:
                    errmsg = str(e)
                    if 'must be between 0 and min' in errmsg:
                        warning('Unrecoverable error: ' + errmsg)
                    else:
                        raise
                except:
                    dead = False
                    raise
                finally:
                    print('==============================================')
                    if dead and remove_dead:
                        ord_sids_path = ord.get_sids_path()
                        ord_bytes_path = ord.get_bytes_path()

                        print('Remove binary file {}'.format(ord_sids_path))
                        try:
                            os.remove(ord_sids_path)
                        except FileNotFoundError:
                            pass

                        print('Remove binary file {}'.format(ord_bytes_path))
                        try:
                            os.remove(ord_bytes_path)
                        except FileNotFoundError:
                            pass

                        print('Remove object')
                        ord.delete()
