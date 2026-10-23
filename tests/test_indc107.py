"""External-source binding and independently specified replacement witnesses."""
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from evaluation.confirmation import cases, indc107, references
from experiments.confirmation_volume_review import analytic
from prompts import confirmation

CASE='indc107_reflective_pin'


class Indc107Tests(unittest.TestCase):
    def test_source_parameters_match_pinned_xml_and_literal_requirements(self):
        indc107.verify_source()
        geometry=ET.parse(indc107.UPSTREAM/'geometry.xml').getroot()
        materials=ET.parse(indc107.UPSTREAM/'materials.xml').getroot()
        self.assertEqual(geometry.find("./surface[@id='1']").get('coeffs').split(),['0.','0.','1.27'])
        self.assertEqual(materials.find("./material[@id='1']/density").get('value'),'18.8')
        self.assertEqual(cases.materials(CASE)['uranium_metal']['atoms'],{'U235':.98,'U238':99.02})
        self.assertEqual(cases.materials(CASE)['water']['density'],1.)
        for p,role in [([0,0,0],'uranium_metal'),([1.2699,0,.99],'uranium_metal'),
                       ([1.2701,0,.99],'water'),([2.,2.,0],'water'),
                       ([0,0,1.0001],'outside'),([2.5401,0,0],'outside')]:
            self.assertEqual(cases.expected(CASE,p),role)
        self.assertEqual(cases.SPECS[CASE]['boundary'],'reflective')
        self.assertTrue(all(r['expected']=='reflective' for r in cases.requirements(CASE)['requirements'] if r['property']=='boundary_type'))
        total,volumes=analytic(CASE)
        self.assertAlmostEqual(total,5.08**2*2)
        self.assertAlmostEqual(volumes['uranium_metal'],math.pi*1.27**2*2)
        points,groups=cases.probes(CASE)
        self.assertTrue(any(math.hypot(p[0],p[1])>1.27 and math.hypot(p[0],p[1])<1.271 for p,g in zip(points,groups) if g=='interfaces'))

    def test_changed_upstream_bytes_and_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'upstream';shutil.copytree(indc107.UPSTREAM,folder)
            (folder/'geometry.xml').write_bytes((folder/'geometry.xml').read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'upstream file changed'):
                indc107.verify_source(folder)
            shutil.copyfile(indc107.UPSTREAM/'geometry.xml',folder/'geometry.xml')
            (folder/'geometry.xml').unlink();(folder/'geometry.xml').symlink_to(indc107.UPSTREAM/'geometry.xml')
            with self.assertRaises((ValueError,OSError)):
                indc107.verify_source(folder)

    def test_previous_release_retains_failed_case_and_current_prompt_is_public_only(self):
        old=json.loads((confirmation.public.PROMPT_ROOT/'confirmation_v1/manifest.json').read_text())
        current,_=confirmation.suite()
        self.assertIn('perforated_mixture_block',[r['id'] for r in old['tasks']])
        self.assertNotIn('perforated_mixture_block',confirmation.TASKS)
        self.assertEqual(current['tasks'][5]['family'],'external_control')
        prompt=confirmation.build_prompt(CASE)
        self.assertIn(indc107.COMMIT,prompt)
        for private in ('scratch/','def build_model','keff =','primary_mean'):
            self.assertNotIn(private,prompt)
        with self.assertRaises(ValueError):confirmation.build_prompt('perforated_mixture_block')

    def test_original_identity_admission_requires_unchanged_physical_contract(self):
        proof=references.compatibility()
        recorded=proof['previous_identities'][0]
        self.assertTrue(references.identity_matches('offset_plate_bank',recorded))
        self.assertFalse(references.identity_matches(CASE,recorded))
        with patch.object(cases,'temperature',return_value=800.):
            self.assertFalse(references.identity_matches('offset_plate_bank',recorded))
        bad=dict(recorded);bad['evaluation/scientific/worker.py']='0'*64
        self.assertFalse(references.identity_matches('offset_plate_bank',bad))
