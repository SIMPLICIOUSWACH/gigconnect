from django.conf import settings
from django.core.mail import send_mail

from .tokens import make_email_verification_token


def send_verification_email(user):
    token = make_email_verification_token(user)
    link = f'{settings.FRONTEND_URL}/verify-email/{token}'
    send_mail(
        subject='Verify your GigConnect email',
        message=f'Hi {user.full_name},\n\nVerify your email by visiting:\n{link}\n\nThis link expires in 24 hours.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
