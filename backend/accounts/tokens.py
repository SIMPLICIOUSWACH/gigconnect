from django.core import signing

EMAIL_VERIFICATION_SALT = 'accounts.email-verification'
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24  # 24 hours


def make_email_verification_token(user):
    return signing.dumps({'user_id': str(user.id)}, salt=EMAIL_VERIFICATION_SALT)


def read_email_verification_token(token):
    """Raises signing.BadSignature / signing.SignatureExpired on failure."""
    return signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=EMAIL_VERIFICATION_MAX_AGE)
