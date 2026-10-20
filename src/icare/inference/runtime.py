"""Shared CPU runtime settings; importing this module does not load ONNX."""
from pathlib import Path


def cpu_session(model_path: Path):
    import onnxruntime as ort

    # Small, independent pools avoid CPU oversubscription between the two models.
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(model_path), sess_options=options,
                               providers=["CPUExecutionProvider"])
