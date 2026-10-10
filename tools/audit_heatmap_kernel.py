"""Compare Gaussian stencils with the pinned MMAction2 v1.2.0 source.

This audits only the joint heatmap kernel at identical transformed coordinates;
it is not validation-pipeline, temporal-sampling, or model-output parity.
The upstream source is supplied explicitly and checked against its recorded hash.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import typing
import numpy as np
from icare_app.posec3d_bridge import pose_sequence_to_heatmaps

SOURCE_URL = 'https://raw.githubusercontent.com/open-mmlab/mmaction2/v1.2.0/mmaction/datasets/transforms/pose_transforms.py'


def compare(source: Path, expected_sha256: str) -> dict:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError('Upstream source hash does not match the reviewed reference.')
    tree = ast.parse(raw.decode('utf-8'))
    reference = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'GeneratePoseTarget')
    # Compile only the two reviewed numeric methods, without imports/registries.
    reference.decorator_list = []
    reference.bases = [ast.Name(id='object', ctx=ast.Load())]
    reference.body = [node for node in reference.body if isinstance(node, ast.FunctionDef) and node.name in ('__init__', 'generate_a_heatmap')]
    namespace = {'np': np, 'Tuple': typing.Tuple}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[reference], type_ignores=[])), str(source), 'exec'), namespace)
    generator = namespace['GeneratePoseTarget'](sigma=.6)
    cases = []
    for x, y, score in [(12., 18., .9), (12.3, 18.7, .9), (31.9, 1.2, 1.4), (.1, .2, .5)]:
        points = np.zeros((1, 17, 3), np.float32)
        points[0, 0] = [1., 1., .9]
        points[0, 1] = [63., 63., .9]
        points[0, 2] = [x, y, score]
        # Normalize reference coordinates identically to the deployed spatial
        # transform, isolating only the Gaussian kernel difference.
        valid = points[..., 2] >= .01
        low = np.array([points[..., 0][valid].min(), points[..., 1][valid].min()])
        high = np.array([points[..., 0][valid].max(), points[..., 1][valid].max()])
        side = max(float((high-low).max()), 1.) * 1.25
        origin = (low+high)*.5 - side*.5
        transformed = points.copy()
        transformed[..., :2] = (transformed[..., :2]-origin)*(64./side)
        upstream = np.zeros((64, 64), np.float32)
        generator.generate_a_heatmap(upstream, transformed[:,2,:2], transformed[:,2,2])
        deployed = pose_sequence_to_heatmaps(points)[2,0]
        delta = np.abs(upstream-deployed)
        cases.append({'center_xy':[x,y], 'score':score, 'max_absolute_difference':float(delta.max()),
                      'mean_absolute_difference':float(delta.mean())})
    return {'upstream_url':SOURCE_URL, 'upstream_sha256':digest, 'scope':'Gaussian kernel only at identical transformed coordinates',
            'full_pipeline_parity':False, 'cases':cases, 'max_absolute_difference':max(case['max_absolute_difference'] for case in cases),
            'finding':'Kernel stencils differ. Full validation-pipeline parity must not be claimed; deployed preprocessing was not changed.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-source',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--output',type=Path,default=Path('artifacts/evaluation/heatmap_kernel_audit.json'))
    args=parser.parse_args()
    result=compare(args.upstream_source,args.expected_sha256)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
