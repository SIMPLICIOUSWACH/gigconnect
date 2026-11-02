import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Client'
        FREELANCER = 'freelancer', 'Freelancer'
        ADMIN = 'admin', 'Admin'

    class AccountStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    # Optional, for M-Pesa payments later. Stored as +254XXXXXXXXX (see phones.py) and never verified.
    phone = models.CharField(max_length=20, blank=True, default='')
    role = models.CharField(max_length=20, choices=Role.choices)
    is_email_verified = models.BooleanField(default=False)
    is_profile_complete = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    # Set by an admin. A suspended user can't log in and their tokens stop working; see accounts/authentication.py.
    account_status = models.CharField(max_length=20, choices=AccountStatus.choices, default=AccountStatus.ACTIVE)
    suspended_reason = models.TextField(blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    # Set by the seed and data-pipeline commands. The profile rows hang off the user, so this one
    # flag covers them too.
    is_synthetic = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'role']

    def __str__(self):
        return self.email

    @property
    def is_suspended(self):
        return self.account_status == self.AccountStatus.SUSPENDED
