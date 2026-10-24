"""Enrolled residents for face naming: photos in, face embeddings out (photos are never kept)."""
from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

import numpy as np

from icare.inference.identity import FaceError, FaceModels, new_resident, read_gallery, write_gallery

MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 15 * 1024 * 1024


class Residents:
    def __init__(self, gallery_path: Path, models: FaceModels | None) -> None:
        self.path, self.models = Path(gallery_path), models
        self._lock = threading.Lock()

    def listing(self) -> dict[str, Any]:
        return {"residents": [_document(r) for r in read_gallery(self.path)],
                "face_models_ready": self.models is not None}

    def enrol(self, name: str, room: str | None, photos: list[bytes]) -> dict[str, Any]:
        import cv2

        name, room = name.strip(), (room or "").strip() or None
        if not name or len(name) > 80:
            raise FaceError("invalid_name", "Enter the resident's name (at most 80 characters).")
        if not 1 <= len(photos) <= MAX_PHOTOS:
            raise FaceError("invalid_photos", f"Add between 1 and {MAX_PHOTOS} photos.")
        if self.models is None:
            raise FaceError("face_models_unavailable", "Face models are not installed on this computer.")
        embeddings = []
        for data in photos:
            if len(data) > MAX_PHOTO_BYTES:
                raise FaceError("invalid_image", "Each photo must be at most 15 MB.")
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise FaceError("invalid_image", "A photo could not be read. Use JPEG or PNG.")
            embeddings.append(self.models.enrolment_embedding(image))
        resident = new_resident(name, room, embeddings)
        with self._lock:
            residents = [r for r in read_gallery(self.path) if r["name"].casefold() != name.casefold()]
            write_gallery(self.path, residents + [resident])  # re-enrolling a name replaces it
        return _document(resident)

    def delete(self, resident_id: str) -> bool:
        with self._lock:
            residents = read_gallery(self.path)
            kept = [r for r in residents if r.get("resident_id") != resident_id]
            if len(kept) == len(residents):
                return False
            write_gallery(self.path, kept)
            return True


def _document(resident: dict[str, Any]) -> dict[str, Any]:
    return {"resident_id": resident["resident_id"], "name": resident["name"], "room": resident.get("room"),
            "photo_count": len(resident.get("embeddings", [])), "created_at_utc": resident["created_at_utc"]}
