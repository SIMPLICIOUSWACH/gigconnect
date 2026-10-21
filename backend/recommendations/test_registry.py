import logging
from unittest import mock

import joblib
from django.test import override_settings

from . import registry
from .models import RecommenderModelVersion
from .test_base import RecommenderTestBase
from .training import COLLABORATIVE_FILE, VECTORISER_FILE, train


class RegistryTests(RecommenderTestBase):
    def train(self):
        return train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)

    def test_switched_off_means_disabled_even_when_a_model_exists(self):
        self.train()
        with override_settings(RECOMMENDATIONS_ENABLED=False):
            result = registry.availability()
        self.assertFalse(result.available)
        self.assertEqual(result.reason, registry.DISABLED)

    def test_no_trained_model_means_unavailable(self):
        result = registry.availability()
        self.assertFalse(result.available)
        self.assertEqual(result.reason, registry.MODEL_UNAVAILABLE)

    def test_after_training_the_model_loads_with_both_parts(self):
        row = self.train()
        result = registry.availability()
        self.assertTrue(result.available)
        self.assertEqual(result.model.version.id, row.id)
        self.assertTrue(hasattr(result.model.vectoriser, 'transform'))
        self.assertIsNotNone(result.model.collaborative)

    def test_a_model_trained_without_the_collaborative_part_loads_with_content_only(self):
        from gigs.models import GigInteraction
        GigInteraction.objects.all().delete()
        self.train()
        model = registry.availability().model
        self.assertIsNotNone(model)
        self.assertIsNone(model.collaborative)

    def test_the_model_is_read_from_disk_once_not_on_every_request(self):
        self.train()
        with mock.patch('recommendations.registry.joblib.load', wraps=joblib.load) as load:
            for _ in range(5):
                registry.availability()
        self.assertEqual(load.call_count, 2)  # the vectoriser and the collaborative model, once

    def test_asking_again_inside_the_cache_time_makes_no_database_query(self):
        self.train()
        registry.availability()
        with self.assertNumQueries(0):
            registry.availability()

    def test_a_newer_model_is_picked_up_once_the_cache_time_is_up(self):
        first = self.train()
        self.assertEqual(registry.availability().model.version.id, first.id)
        second = self.train()
        # Still inside the cache time, so the old one is still being served.
        self.assertEqual(registry.availability().model.version.id, first.id)
        with override_settings(RECOMMENDER_MODEL_CACHE_SECONDS=0):
            self.assertEqual(registry.availability().model.version.id, second.id)

    def test_clearing_the_cache_makes_the_next_request_look_again(self):
        first = self.train()
        registry.availability()
        second = self.train()
        registry.clear_cache()
        self.assertEqual(registry.availability().model.version.id, second.id)
        self.assertNotEqual(first.id, second.id)


class BrokenModelTests(RecommenderTestBase):
    """A missing or broken model is an ordinary answer ("not available"), never an error."""

    def train(self):
        return train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)

    def test_missing_files_mean_unavailable_and_nothing_is_raised(self):
        row = self.train()
        (self.artifact_dir / row.folder / VECTORISER_FILE).unlink()
        with self.assertLogs('recommendations.registry', level=logging.WARNING):
            result = registry.availability()
        self.assertFalse(result.available)
        self.assertEqual(result.reason, registry.MODEL_UNAVAILABLE)

    def test_a_missing_artifact_folder_means_unavailable(self):
        import shutil
        shutil.rmtree(self.artifact_dir / self.train().folder)
        with self.assertLogs('recommendations.registry', level=logging.WARNING):
            self.assertFalse(registry.availability().available)

    def test_a_corrupt_file_means_unavailable(self):
        row = self.train()
        (self.artifact_dir / row.folder / VECTORISER_FILE).write_bytes(b'this is not a model')
        with self.assertLogs('recommendations.registry', level=logging.WARNING):
            self.assertFalse(registry.availability().available)

    def test_a_file_that_is_not_a_vectoriser_is_refused(self):
        row = self.train()
        joblib.dump({'not': 'a vectoriser'}, self.artifact_dir / row.folder / VECTORISER_FILE)
        with self.assertLogs('recommendations.registry', level=logging.WARNING):
            self.assertFalse(registry.availability().available)

    def test_a_missing_collaborative_file_means_unavailable(self):
        row = self.train()
        (self.artifact_dir / row.folder / COLLABORATIVE_FILE).unlink()
        with self.assertLogs('recommendations.registry', level=logging.WARNING):
            self.assertFalse(registry.availability().available)

    def test_if_the_newest_model_cannot_be_read_the_previous_one_keeps_serving(self):
        first = self.train()
        self.assertTrue(registry.availability().available)
        second = self.train()
        (self.artifact_dir / second.folder / VECTORISER_FILE).write_bytes(b'broken')
        with override_settings(RECOMMENDER_MODEL_CACHE_SECONDS=0), self.assertLogs(
            'recommendations.registry', level=logging.WARNING,
        ):
            result = registry.availability()
        self.assertTrue(result.available)
        self.assertEqual(result.model.version.id, first.id)

    def test_a_database_problem_is_not_raised(self):
        with mock.patch.object(RecommenderModelVersion.objects, 'order_by', side_effect=RuntimeError('no table')):
            with self.assertLogs('recommendations.registry', level=logging.WARNING):
                result = registry.availability()
        self.assertFalse(result.available)

    def test_importing_the_module_loads_nothing(self):
        import importlib
        with mock.patch('joblib.load') as load:
            importlib.reload(registry)
        load.assert_not_called()
