"""Independent truth-table checks for exact reduction, without OpenMC loading."""
import importlib.util
import itertools
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import patch


def load_worker():
    path = Path(__file__).resolve().parents[1]/'evaluation/scientific/boundary_worker_v2.py'
    spec = importlib.util.spec_from_file_location('boundary_reduction_test', path)
    worker = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'openmc': types.ModuleType('openmc')}):
        spec.loader.exec_module(worker)
    return worker


def truth(expr, bits):
    if isinstance(expr, bool):
        return expr
    if expr[0] == 'atom':
        return bits[expr[1]] == expr[2]
    values = [truth(child,bits) for child in expr[1]]
    return all(values) if expr[0] == 'and' else any(values)


class BooleanReduction(unittest.TestCase):
    def test_reduction_preserves_independent_truth_tables(self):
        worker = load_worker()
        rng = random.Random(8191)
        def expression(depth):
            if depth == 0 or rng.random() < .35:
                return ('atom',rng.randrange(4),bool(rng.randrange(2)))
            return (rng.choice(['and','or']),tuple(expression(depth-1) for _ in range(rng.randrange(2,5))))
        def simplify(expr):
            if expr[0] == 'atom':
                return expr
            return worker.junction(expr[0],map(simplify,expr[1]),lambda n=1: None)
        for _ in range(250):
            original = expression(4)
            reduced = simplify(original)
            for bits in itertools.product([False,True],repeat=4):
                self.assertEqual(truth(original,bits),truth(reduced,bits),(original,reduced,bits))

    def test_partition_cover_reduces_without_enumeration(self):
        worker = load_worker()
        outside = [('atom',i,True) for i in range(75)]
        inside = [('atom',i,False) for i in range(75)]
        # Independent identity: inside any concentric ring OR outside all pins
        # covers the active region. No radius or expected observer value is used.
        regions = []
        for i in range(0,75,3):
            regions += [inside[i],('and',(outside[i],inside[i+1])),
                        ('and',(outside[i+1],inside[i+2]))]
        regions.append(('and',tuple(outside[2::3])))
        self.assertIs(worker.junction('or',regions,lambda n=1: None),True)

    def test_reduction_work_is_bounded(self):
        worker = load_worker()
        count = 0
        def tick(n=1):
            nonlocal count
            count += n
            if count > 10:
                raise worker.CoverageLimit('work_units',10,count)
        with self.assertRaises(worker.CoverageLimit) as caught:
            worker.junction('and',[('atom',i,True) for i in range(20)],tick)
        self.assertEqual(caught.exception.detail,dict(guard='work_units',configured_bound=10,attempted=11))
