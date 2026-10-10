"""Spawnable TEST ADAPTER. Never a production loader or model-evidence source."""
import os
import time


class Adapter:
    ready = True
    model_version = 'test-adapter-not-a-model'

    def analyze_video(self, path, **callbacks):
        if path.name == 'hang.mp4':
            time.sleep(60)  # Deliberately ignores cancellation, like a stuck native call.
        if path.name == 'crash.mp4':
            os._exit(3)
        callbacks['on_prediction']({'timestamp_seconds': 2.0, 'fall_probability': 0.1})
        return {'duration_seconds': 3, 'frame_width': 640, 'frame_height': 480}

    def close(self):
        pass


def create_engine(config):
    return Adapter()
