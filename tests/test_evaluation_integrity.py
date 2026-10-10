"""Regression cases for failed jobs and unverified evidence boundaries."""
from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest

from evaluation.benchmark_harness import BenchmarkHarness, ClipAnnotation, EvaluationRecord
from evaluation.run_benchmarks import load_annotations_from_catalog


def record(name, label, error=None, incidents=0):
    return EvaluationRecord(name, label, 'Failed (no_person)' if error else ('fall' if incidents else 'no_fall'),
        None if error else .1, incidents, None, None, 2., 12, 2, 6., None, None, None, error)


class EvaluationIntegrityTests(unittest.TestCase):
    def test_failed_normal_analysis_is_never_a_true_negative(self):
        a = ClipAnnotation('bad', Path('bad.mp4'), 'no_fall', duration_seconds=3600)
        m = BenchmarkHarness.compute_metrics([record('bad', 'no_fall', 'no_person')], [a])
        self.assertEqual((m.tn, m.failed_clips, m.successful_clips), (0, 1, 0))
        self.assertIsNone(m.overall_accuracy)
        self.assertIsNone(m.false_alarms_per_hour)

    def test_unverified_labels_produce_runtime_measurements_without_accuracy(self):
        a = ClipAnnotation('local', Path('local.mp4'), 'no_fall', label_status='pending')
        m = BenchmarkHarness.compute_metrics([record('local', 'no_fall')], [a])
        self.assertEqual(m.unverified_labels, 1)
        self.assertIsNone(m.overall_accuracy)
        self.assertEqual(m.avg_fps, 6.)

    def test_false_alarm_denominator_uses_only_verified_normal_exposure(self):
        a = [ClipAnnotation('normal', Path('n.mp4'), 'no_fall', duration_seconds=3600),
             ClipAnnotation('fall', Path('f.mp4'), 'fall', duration_seconds=3600)]
        m = BenchmarkHarness.compute_metrics([record('normal', 'no_fall', incidents=1), record('fall', 'fall', incidents=1)], a)
        self.assertEqual(m.normal_observed_hours, 1.)
        self.assertEqual(m.false_alarms_per_hour, 1.)

    def test_manifest_repository_relative_paths_are_not_prefixed_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); examples = root / 'examples'; examples.mkdir()
            manifest = examples / 'manifest.json'
            manifest.write_text(json.dumps({'clips': [{'id':'clip','filename':'examples/clip.mp4','expected_outcome':'fall'}]}))
            annotations, _ = load_annotations_from_catalog(manifest)
            self.assertEqual(annotations[0].filename, (examples / 'clip.mp4').resolve())
            self.assertEqual(annotations[0].label_status, 'pending')


if __name__ == '__main__': unittest.main()
