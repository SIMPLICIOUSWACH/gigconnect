import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from accounts.models import User

PASSWORD_ENV = 'GIGCONNECT_ADMIN_PASSWORD'


class Command(BaseCommand):
    help = (
        'Create a GigConnect admin: role admin, email and phone marked verified, and is_staff so Django\'s '
        'own /admin/ login also accepts them. It asks for the password; with --noinput it reads '
        f'{PASSWORD_ENV} instead. Sign-up can never create an admin, so this is the only way.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--full-name', default='GigConnect Admin')
        parser.add_argument('--phone', default='')
        parser.add_argument('--noinput', action='store_true', help=f'Read the password from {PASSWORD_ENV}.')

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options['email'].strip())
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError(f'"{email}" is not a valid email address.') from error
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f'An account with the email {email} already exists.')

        password = self.read_password(options['noinput'])
        user = User(email=email, full_name=options['full_name'], phone=options['phone'], role=User.Role.ADMIN)
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(' '.join(error.messages)) from error

        User.objects.create_user(
            email=email,
            password=password,
            full_name=options['full_name'],
            phone=options['phone'],
            role=User.Role.ADMIN,
            is_staff=True,
            is_email_verified=True,
            is_phone_verified=True,
            is_profile_complete=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Created admin {email}.'))

    def read_password(self, noinput):
        if noinput:
            password = os.environ.get(PASSWORD_ENV, '')
            if not password:
                raise CommandError(f'--noinput needs the password in {PASSWORD_ENV}.')
            return password
        password = getpass.getpass('Password: ')
        if password != getpass.getpass('Password (again): '):
            raise CommandError('The passwords did not match.')
        return password
