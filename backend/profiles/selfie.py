"""
The live selfie for ID verification: the random challenge shown before the photo, the checks on the photo itself, and
counting the faces in it.

The server cannot prove a photo came straight from the camera. A fresh, single-use challenge that expires after ten
minutes means an old photo would not show the right gesture, and the admin checks that the gesture was really done.
"""

import secrets
from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

CHALLENGE_LIFETIME = timedelta(minutes=10)
MAX_SIZE_BYTES = 5 * 1024 * 1024
MIN_LONG_SIDE = 640
MIN_SHORT_SIDE = 480
MAX_PIXELS = 40_000_000  # far above any phone camera, and well below a decompression bomb
JPEG_QUALITY = 90

GESTURES = (
    'show 1 finger',
    'show 2 fingers',
    'show 3 fingers',
    'show 4 fingers',
    'show 5 fingers',
    'give a thumbs up',
    'touch your left ear',
    'touch your right ear',
    'touch your nose',
    'touch your chin',
)

# A face counts if it is at least this share of the width of the largest face. The face printed on the ID card someone
# is holding is much smaller, so it is not counted as a second person.
MIN_FACE_SHARE = 1 / 3

RETAKE_NO_FACE = 'We could not find your face. Face the camera in good light, fill the oval, and take the photo again.'
RETAKE_MANY_FACES = 'We found more than one face. Make sure only you are in the photo, then take it again.'


def new_challenge_text():
    return f'Hold your ID next to your face and {secrets.choice(GESTURES)}.'


def challenge_is_usable(challenge, now=None):
    now = now or timezone.now()
    return challenge.used_at is None and challenge.issued_at + CHALLENGE_LIFETIME > now


def process_selfie(upload):
    """
    Check the uploaded photo and return it re-encoded as a JPEG with nothing but the pixels: no EXIF, so no location,
    camera or time details. Returns (ContentFile, Pillow image). Raises a ValidationError the person can act on.
    """
    if upload.size > MAX_SIZE_BYTES:
        raise serializers.ValidationError('The photo must be 5 MB or smaller.')
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(upload) as opened:
            if opened.format not in ('JPEG', 'PNG'):
                raise serializers.ValidationError('The photo must be a JPEG or PNG image.')
            image = ImageOps.exif_transpose(opened).convert('RGB')
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise serializers.ValidationError('This file is not a photo we can read.') from error

    long_side, short_side = max(image.size), min(image.size)
    if long_side < MIN_LONG_SIDE or short_side < MIN_SHORT_SIDE:
        raise serializers.ValidationError(
            f'The photo is too small ({image.width} x {image.height}). It needs to be at least 640 x 480.'
        )

    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=JPEG_QUALITY)  # no exif= argument, so none is written
    return ContentFile(buffer.getvalue(), name='selfie.jpg'), image


def detect_faces(image):
    """Faces found by OpenCV's Haar cascade, as (x, y, width, height) boxes. Imported late so startup stays fast."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    smallest = max(24, min(gray.shape) // 20)
    found = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(smallest, smallest))
    return [tuple(int(value) for value in box) for box in found]


def counted_faces(boxes, min_share=MIN_FACE_SHARE):
    """The faces that count: those at least `min_share` of the largest face's width."""
    if not boxes:
        return []
    largest = max(box[2] for box in boxes)
    return [box for box in boxes if box[2] >= largest * min_share]


def face_problem(image):
    """None if there is exactly one face that counts, or the message asking for a retake."""
    faces = counted_faces(detect_faces(image))
    if not faces:
        return RETAKE_NO_FACE
    if len(faces) > 1:
        return RETAKE_MANY_FACES
    return None
