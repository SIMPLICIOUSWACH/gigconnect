"""
Which files count as an ID document. An admin views these in the browser, so anything that could carry a script, such
as HTML or SVG, must never be stored or shown inline.
"""

import os

from rest_framework import serializers

MAX_SIZE_BYTES = 5 * 1024 * 1024

# Extension -> (content type, the bytes a real file of that type starts with).
ALLOWED_TYPES = {
    '.pdf': ('application/pdf', b'%PDF-'),
    '.jpg': ('image/jpeg', b'\xff\xd8\xff'),
    '.jpeg': ('image/jpeg', b'\xff\xd8\xff'),
    '.png': ('image/png', b'\x89PNG\r\n\x1a\n'),
}

SAFE_FALLBACK_TYPE = 'application/octet-stream'


def _extension(name):
    return os.path.splitext(name)[1].lower()


def validate_id_document(upload):
    """Checks the extension and the file's first bytes, because the name and the browser's stated type can both lie."""
    allowed = ALLOWED_TYPES.get(_extension(upload.name))
    if allowed is None:
        raise serializers.ValidationError('Upload a PDF, JPG or PNG file.')
    if upload.size > MAX_SIZE_BYTES:
        raise serializers.ValidationError('The file must be 5 MB or smaller.')
    signature = allowed[1]
    upload.seek(0)
    start = upload.read(len(signature))
    upload.seek(0)
    if start != signature:
        raise serializers.ValidationError('This file is not a real PDF, JPG or PNG.')
    return upload


def can_show_inline(name):
    return _extension(name) in ALLOWED_TYPES


def content_type_for(name):
    """The type to serve a stored file as. Files from before these checks may be anything, so they get a neutral one."""
    allowed = ALLOWED_TYPES.get(_extension(name))
    return allowed[0] if allowed else SAFE_FALLBACK_TYPE
