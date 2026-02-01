import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    from insightface.app import FaceAnalysis
except Exception as e:
    FaceAnalysis = None


class InsightFaceRecognizer:
    """
    Face recognizer using InsightFace (ArcFace) embeddings and cosine similarity.

    Loads known faces from a directory structure:
      known_faces_dir/
        PersonA/
          img1.jpg
          img2.png
        PersonB/
          img1.jpg
    """

    def __init__(
        self,
        known_faces_dir: str,
        det_size: Tuple[int, int] = (640, 640),
        provider: str = "cpu",
        similarity_threshold: float = 0.35,
        min_face_size: int = 40,
    ):
        if FaceAnalysis is None:
            raise RuntimeError("InsightFace is not available. Please install insightface.")

        self.known_faces_dir = Path(known_faces_dir)
        self.det_size = det_size
        self.similarity_threshold = similarity_threshold
        self.min_face_size = min_face_size
        self.app = FaceAnalysis(providers=["CPUExecutionProvider"] if provider == "cpu" else None)
        # ctx_id: -1 for CPU; 0+ for GPU
        self.app.prepare(ctx_id=-1 if provider == "cpu" else 0, det_size=det_size)

        # name -> list of embeddings
        self.known_db: Dict[str, List[np.ndarray]] = {}

        self._load_known_faces()

    def _load_known_faces(self):
        if not self.known_faces_dir.exists():
            raise FileNotFoundError(f"Known faces directory not found: {self.known_faces_dir}")

        for person_dir in self.known_faces_dir.iterdir():
            if not person_dir.is_dir():
                continue
            person_name = person_dir.name
            embeddings: List[np.ndarray] = []
            for img_path in person_dir.glob("**/*"):
                if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
                    continue
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                faces = self.app.get(img)
                if not faces:
                    continue
                # pick largest face
                face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                emb = getattr(face, "normed_embedding", None)
                if emb is None:
                    continue
                embeddings.append(np.asarray(emb, dtype=np.float32))
            if embeddings:
                self.known_db[person_name] = embeddings

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        # vectors are already normalized in InsightFace
        return float(np.dot(a, b))

    def recognize(self, crop_bgr: np.ndarray) -> Tuple[Optional[str], Optional[float]]:
        """
        Recognize identity from a cropped face image.

        Returns: (name, score) or (None, None) when unknown.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return None, None
        h, w = crop_bgr.shape[:2]
        if min(h, w) < self.min_face_size:
            return None, None

        faces = self.app.get(crop_bgr)
        if not faces:
            return None, None

        # Use largest detected face within crop
        face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        emb = getattr(face, "normed_embedding", None)
        if emb is None:
            return None, None
        emb = np.asarray(emb, dtype=np.float32)

        best_name = None
        best_score = -1.0

        for name, embs in self.known_db.items():
            # compare against all samples for this identity
            for ref in embs:
                score = self._cosine_sim(emb, ref)
                if score > best_score:
                    best_score = score
                    best_name = name

        if best_score >= self.similarity_threshold:
            return best_name, best_score
        return None, None