from koe.feature_utils import _calculate_similarity
from koe.management.abstract_commands.recreate_persisted_objects import RecreateIdsPersistentObjects
from koe.models import SimilarityIndex
from koe.task import ConsoleTaskRunner


class Command(RecreateIdsPersistentObjects):
    def perform_action(self, when, remove_dead):
        sims = SimilarityIndex.objects.all()
        for sim in sims:
            need_recalculate = self.check_rebuild_necessary(sim, when)

            if need_recalculate:
                runner = ConsoleTaskRunner(prefix="Recalculate similarity {}".format(sim))
                _calculate_similarity(sim, runner)
