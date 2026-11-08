import re

from django.db import migrations, models

# A copy of the rule in accounts/phones.py as it stood when this ran, so later changes there can't alter this migration.
MOBILE = re.compile(r'^(?:\+254|254|0)?([71]\d{8})$')


def normalise_phones(apps, schema_editor):
    """Every number becomes +254XXXXXXXXX. One that can't be read as a Kenyan mobile is blanked."""
    User = apps.get_model('accounts', 'User')
    changed = []
    for user in User.objects.exclude(phone='').only('id', 'phone'):
        match = MOBILE.match(re.sub(r'[\s\-()]', '', user.phone))
        phone = f'+254{match.group(1)}' if match else ''
        if phone != user.phone:
            user.phone = phone
            changed.append(user)
    User.objects.bulk_update(changed, ['phone'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_account_status'),
    ]

    # The data step is last: PostgreSQL can refuse to alter a table that was updated earlier in the same transaction.
    operations = [
        migrations.DeleteModel(name='OTP'),
        migrations.RemoveField(model_name='user', name='is_phone_verified'),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        # The old numbers and flags are not kept, so going back leaves the numbers as they are.
        migrations.RunPython(normalise_phones, migrations.RunPython.noop),
    ]
