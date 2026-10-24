"""Fixture integrity only; native observer qualification is a separate command."""
import unittest
import xml.etree.ElementTree as ET

from evaluation.representation import controls
from evaluation.scientific.inspection import admit


class RepresentationControls(unittest.TestCase):
    def test_public_xml_is_admitted_and_variants_are_distinct(self):
        rows = controls.boundary_controls()
        self.assertEqual(len({r['id'] for r in rows}), 16)
        self.assertEqual(len({r['xml'] for r in rows}), 16)
        for row in rows:
            with self.subTest(row=row['id']):
                admit(row['xml'])

    def test_renumbering_preserves_material_assignments_without_original_ids(self):
        root = controls.renumber(controls.wrapped())
        self.assertEqual(len(root.findall('geometry/cell')), 28)
        self.assertTrue(all(int(c.get('id')) > 500 for c in root.findall('geometry/cell')))
        self.assertEqual(sum(c.get('material') == '1' for c in root.findall('geometry/cell')), 8)

    def test_defects_have_independent_positive_volume_witnesses(self):
        rows = {r['id']:r for r in controls.boundary_controls()}
        self.assertEqual(rows['missing-lower-slab']['witness'], [-3., -3., -2.5])
        self.assertEqual(rows['unbounded-lower-water']['witness'], [-3., -3., -3.5])
        self.assertEqual(rows['localized-overlap']['expected'], 'geometry_overlap')


if __name__ == '__main__':
    unittest.main()
