import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    """
    Files no URL can reach, kept in settings.PRIVATE_MEDIA_ROOT, outside MEDIA_ROOT. With no base URL, asking a file for
    its `.url` raises an error, so one can't be handed out by accident. They are read only through a view that checks
    who is asking, such as the admin ID document endpoint.
    """

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None
