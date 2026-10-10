# Dataset access and evidence

The dataset and split manifests are not included in Git. Obtain the original
paired videos and COCO-17 pose CSVs under the dataset's distribution terms.

```text
Fall/Raw_Video/
Fall/Keypoints_CSV/
No_Fall/Raw_Video/
No_Fall/Keypoints_CSV/
```

The project records 6,988 original pairs and 6,766 samples after cleaning and
exact-pose deduplication. The group-aware split has 4,742 training, 1,013
validation, and 1,011 test samples. See the root README for the full count and
metric tables and [evaluation status](evaluation_status.md) for subject-ID limits.

The project owner identifies the training source as [Fall Video Dataset by payutch](https://www.kaggle.com/datasets/payutch/fall-video-dataset).
Kaggle public metadata (checked 10 October 2026) lists version 1, about 16.1 GB,
and a CC0 label. Its description identifies an aggregation of Fall Vision
(Harvard Dataverse DOI 10.7910/DVN/75QPKK), the Figshare dataset with 2017
activities from 29 subjects, and the Montreal multiple-camera fall dataset.
The aggregator label does not independently verify each original source's
redistribution terms or subject coverage. Exact training version, participant
mapping, split/prediction outputs and source-specific permission remain pending. Do not fill these with
assumptions. The former notebooks and `About Dataset` file have been removed
from the current working tree; Git history retains the earlier versions.

Keep private/local data outside this repository, or in ignored `data/` when
working locally. Record dataset version, split IDs, seed, preprocessing, model
checkpoint, and output evidence for every experiment. Share sanitized summaries
and approved figures through project docs rather than committing raw recordings.
