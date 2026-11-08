from pathlib import Path

from django.conf import settings
from django.core.checks import Warning, register

PUBLIC_FOLDER = 'id_documents'


def public_id_documents():
    """Files still in the public media folder, where a link alone can open them."""
    folder = Path(settings.MEDIA_ROOT) / PUBLIC_FOLDER
    if not folder.is_dir():
        return []
    return [path for path in folder.rglob('*') if path.is_file()]


@register()
def id_documents_are_private(app_configs, **kwargs):
    found = public_id_documents()
    if not found:
        return []
    return [Warning(
        f'{len(found)} ID document(s) are still in the public media folder.',
        hint='Run "python manage.py move_id_documents" to move them to private storage.',
        id='profiles.W001',
    )]


@register()
def id_hash_key_is_set(app_configs, **kwargs):
    if settings.ID_HASH_KEY:
        return []
    return [Warning(
        'ID_HASH_KEY is not set, so ID numbers are hashed with a key derived from SECRET_KEY.',
        hint='Set a long random ID_HASH_KEY in backend/.env once, before real ID checks, and never change it.',
        id='profiles.W002',
    )]
