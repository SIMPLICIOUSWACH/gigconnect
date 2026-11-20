"""
An advisory face-similarity score between the ID photo and the selfie, from OpenCV's YuNet (finds the face) and SFace
(compares two faces). ADVISORY ONLY: it is shown to the admin as a hint and nothing ever approves or rejects a check
because of it.

The two model files come from the official OpenCV Zoo repository (fetch_face_models downloads them and checks each
SHA-256 against the value published there). Without them, or for a PDF ID, the score is "not available".
"""

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

ZOO = 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models'

# name -> (download URL, SHA-256 published in the repository's Git LFS pointer, size in bytes, licence)
MODELS = {
    'face_detection_yunet_2023mar.onnx': (
        f'{ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx',
        '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4', 232589, 'MIT (Shiqi Yu)',
    ),
    'face_recognition_sface_2021dec.onnx': (
        f'{ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx',
        '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79', 38696353, 'Apache-2.0',
    ),
}
DETECTOR, RECOGNISER = MODELS
MODEL_NAME = 'OpenCV SFace 2021dec (cosine), faces found by YuNet 2023mar'
MAX_SIDE = 1280  # larger images are scaled down first: faster, and plenty for a face

NOT_AVAILABLE_PDF = 'not available (PDF)'
NOT_AVAILABLE_MODELS = 'not available (face models not installed)'
NOT_AVAILABLE_ID_FACE = 'not available (no face found on the ID)'
NOT_AVAILABLE_SELFIE_FACE = 'not available (no face found in the selfie)'
NOT_AVAILABLE_ERROR = 'not available (could not compare)'


def model_path(name):
    return Path(settings.FACE_MODELS_DIR) / name


def models_installed():
    return all(model_path(name).is_file() for name in MODELS)


def _read(field):
    import cv2
    import numpy as np

    with field.open('rb') as handle:
        data = np.frombuffer(handle.read(), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None
    scale = MAX_SIDE / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return image


def _largest_face(detector, image):
    """The biggest face YuNet finds, or None. In a selfie with an ID held up, that is the person, not the card."""
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return None
    return max(faces, key=lambda face: face[2] * face[3])


def compare(id_document, selfie):
    """(score, model name or the reason there is no score). The score is a cosine similarity, higher is closer."""
    if id_document.name.lower().endswith('.pdf'):
        return None, NOT_AVAILABLE_PDF
    if not models_installed():
        return None, NOT_AVAILABLE_MODELS

    import cv2

    try:
        id_image, selfie_image = _read(id_document), _read(selfie)
        if id_image is None:
            return None, NOT_AVAILABLE_ID_FACE
        detector = cv2.FaceDetectorYN.create(str(model_path(DETECTOR)), '', (320, 320))
        recogniser = cv2.FaceRecognizerSF.create(str(model_path(RECOGNISER)), '')
        id_face = _largest_face(detector, id_image)
        if id_face is None:
            return None, NOT_AVAILABLE_ID_FACE
        selfie_face = _largest_face(detector, selfie_image)
        if selfie_face is None:
            return None, NOT_AVAILABLE_SELFIE_FACE
        features = [
            recogniser.feature(recogniser.alignCrop(image, face))
            for image, face in ((id_image, id_face), (selfie_image, selfie_face))
        ]
        score = float(recogniser.match(features[0], features[1], cv2.FaceRecognizerSF_FR_COSINE))
    except Exception:
        logger.exception('Face comparison failed.')
        return None, NOT_AVAILABLE_ERROR
    return round(score, 3), MODEL_NAME


def record_face_match(profile):
    """Work out the hint for a check that has both parts. Only ever sets the two hint fields; never the status."""
    if not (profile.id_document and profile.selfie):
        return []
    profile.face_match_score, profile.face_match_model = compare(profile.id_document, profile.selfie)
    return ['face_match_score', 'face_match_model']
