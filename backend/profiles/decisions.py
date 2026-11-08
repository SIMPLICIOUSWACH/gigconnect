"""
The words of an ID check decision, shared by the admin API and the notice the freelancer gets.

Approving needs every item on the checklist ticked. Rejecting needs a reason and says which part must be sent again:
the ID, the selfie or both. The other part is kept.
"""

CHECKLIST = {
    'same_person': 'Same person in both photos',
    'id_matches': 'ID visible in the selfie and matches the uploaded ID',
    'challenge_done': 'Challenge gesture performed correctly',
}

REJECTION_REASONS = {
    'face_mismatch': "The face in the selfie doesn't match the photo on the ID.",
    'challenge_not_performed': "The challenge gesture wasn't done in the selfie.",
    'id_not_visible': "Your ID isn't clearly visible in the selfie.",
    'photo_unclear': 'The photo is unclear.',
    'other': '',
}

REDO_ID, REDO_SELFIE, REDO_BOTH = 'id', 'selfie', 'both'
REDO_CHOICES = (REDO_ID, REDO_SELFIE, REDO_BOTH)
REDO_WORDS = {
    REDO_ID: 'upload your ID again',
    REDO_SELFIE: 'take a new selfie',
    REDO_BOTH: 'upload your ID again and take a new selfie',
}


def rejection_text(code, details):
    """The reason as the freelancer and the audit log see it: the quick reason, then anything the admin added."""
    return ' '.join(part for part in (REJECTION_REASONS.get(code, ''), details.strip()) if part)
