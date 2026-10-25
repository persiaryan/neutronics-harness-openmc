"""Independent flat-cell source support cases; no OpenMC execution."""
import unittest
import xml.etree.ElementTree as ET

from evaluation.representation.controls import source_controls, SOURCE_POINTS
from evaluation.scientific import source_domains


def observed(root):
    cells=root.findall('geometry/cell')
    # Fixture cell declaration order is changed by the renumbering transform.
    # Witness roles are specified independently through literal fixture boxes.
    sorted_cells=sorted(cells,key=lambda c: int(c.get('id')))
    if [int(c.get('id')) for c in sorted_cells]==[1,2,93]:
        owners=[93,2,1]
    elif int(sorted_cells[0].get('id'))>500:
        owners=[511,522,533]
    else:
        owners=[1,2,3]
    materials={int(c.get('id')):int(c.get('material')) for c in cells}
    return dict(observer_version='source-domain-observation-v1',limitations=[],
                cells=[dict(id=cid,material_id=mid) for cid,mid in materials.items()],
                witnesses=[dict(point=p,point_index=i,cell_id=cid,material_id=materials[cid])
                           for i,(p,cid) in enumerate(zip(SOURCE_POINTS,owners))])


class SourceDomains(unittest.TestCase):
    def test_positive_negative_unknown_matrix(self):
        for row in source_controls():
            root=ET.fromstring(row['xml'])
            with self.subTest(control=row['id']):
                result=source_domains.compare(root,observed(root),row['material_fissionability'])
                self.assertIs(result['passed'],row['expected'],result)

    def test_absent_counterexample_is_not_positive_equivalence(self):
        row=next(r for r in source_controls() if r['id']=='missing-fuel-cell')
        root=ET.fromstring(row['xml']); obs=observed(root);obs['witnesses']=[]
        result=source_domains.compare(root,obs,row['material_fissionability'])
        self.assertIsNone(result['passed'])

    def test_unknown_material_and_hierarchy_do_not_pass_domain_equivalence(self):
        row=next(r for r in source_controls() if r['id']=='all-fuel-cells')
        root=ET.fromstring(row['xml']);obs=observed(root)
        self.assertIsNone(source_domains.compare(root,obs,{1:True})['passed'])
        obs['limitations']=['requires_flat_untransformed_material_cells']
        self.assertIsNone(source_domains.compare(root,obs,row['material_fissionability'])['passed'])

    def test_witness_outside_proposal_cannot_refute_source_equivalence(self):
        row=next(r for r in source_controls() if r['id']=='missing-fuel-cell')
        root=ET.fromstring(row['xml']);obs=observed(root)
        for witness in obs['witnesses']: witness['point']=[9,9,9]
        self.assertIsNone(source_domains.compare(root,obs,row['material_fissionability'])['passed'])

    def test_duplicate_and_invalid_ids_are_not_silently_normalized(self):
        row=next(r for r in source_controls() if r['id']=='all-fuel-cells')
        for ids in ('1 1 2','0','not-an-id','999',''):
            root=ET.fromstring(row['xml']);root.find('settings/source/constraints/domain_ids').text=ids
            with self.subTest(ids=ids):
                self.assertIsNone(source_domains.compare(root,observed(root),row['material_fissionability'])['passed'])

    def test_explicit_empty_constraint_is_not_interpreted_as_a_default(self):
        row=next(r for r in source_controls() if r['id']=='all-fuel-cells')
        root=ET.fromstring(row['xml'])
        ET.SubElement(root.find('settings/source/constraints'),'fissionable')
        self.assertIsNone(source_domains.compare(root,observed(root),row['material_fissionability'])['passed'])


if __name__=='__main__': unittest.main()
