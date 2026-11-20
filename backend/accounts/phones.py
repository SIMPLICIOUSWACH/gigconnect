"""
Kenyan mobile numbers, kept as +2547XXXXXXXX or +2541XXXXXXXX. They are for M-Pesa payments later. Nothing verifies them
and nothing sends them a code.
"""

import re

from rest_framework import serializers

MOBILE_PATTERN = re.compile(r'^(?:\+254|254|0)?([71]\d{8})$')
INVALID_MESSAGE = 'Enter a Kenyan mobile number, such as 0712345678 or +254712345678. Landlines are not accepted.'


def normalise_phone(value):
    """The number as +254XXXXXXXXX, an empty string for no number, or None if it isn't a Kenyan mobile."""
    cleaned = re.sub(r'[\s\-()]', '', value or '')
    if not cleaned:
        return ''
    match = MOBILE_PATTERN.match(cleaned)
    return f'+254{match.group(1)}' if match else None


def clean_phone(value):
    """For serializers: the normalised number, or a validation error with the message people see."""
    phone = normalise_phone(value)
    if phone is None:
        raise serializers.ValidationError(INVALID_MESSAGE)
    return phone
