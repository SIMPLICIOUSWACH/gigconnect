import random
from datetime import timedelta

from django.utils import timezone

from .models import OTP
from .sms import SMSProvider

OTP_LIFETIME = timedelta(minutes=5)


def issue_otp(user):
    OTP.objects.filter(user=user, is_used=False).update(is_used=True)
    code = f'{random.randint(0, 999999):06d}'
    OTP.objects.create(user=user, code=code, expires_at=timezone.now() + OTP_LIFETIME)
    SMSProvider.send(user.phone, f'Your GigConnect verification code is {code}')
