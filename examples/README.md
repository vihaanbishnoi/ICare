# Example media and provenance

The two existing clips remain diagnostic inputs. Their previous UR-dataset,
CC-BY license and onset metadata lacked supporting source evidence and have
been removed. Catalog rights and independent labels are pending verification.
The default public API does not list or serve unverified clips.

Set ICARE_ALLOW_UNVERIFIED_EXAMPLES=1 only for local diagnostic executions.
Never use that override for a public release. Verified entries require
rights_status=verified, source_url, license and label_status=verified.
Record the actual originating file/source, permission, independently reviewed
outcome and onset (when known). A model prediction does not establish a label.
The owner's Kaggle training-dataset URL does not identify these two clips.

Private recordings and new datasets belong in ignored data/ or artifacts/.
Do not stage unsafe falls. The report uses confidence/signal traces rather than
redistributing frames from unverified recordings.
