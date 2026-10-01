from django.db import migrations


def report_non_kes_gigs(apps, schema_editor):
    """Report-only: GigConnect is KES-only going forward (see GigValidationMixin), but this
    does not touch existing rows — a silent currency rewrite would corrupt any budget that was
    genuinely entered in another currency before that validation existed."""
    Gig = apps.get_model('gigs', 'Gig')
    non_kes = Gig.objects.exclude(currency='KES')
    count = non_kes.count()
    if count:
        sample_ids = list(non_kes.values_list('id', flat=True)[:20])
        print(
            f'\n[0007_report_non_kes_gigs] WARNING: {count} existing gig(s) have a non-KES '
            f'currency. New gigs with a non-KES currency are now rejected at the API. '
            f'Sample id(s): {sample_ids}'
        )
    else:
        print('\n[0007_report_non_kes_gigs] No non-KES gigs found.')


class Migration(migrations.Migration):

    dependencies = [
        ('gigs', '0006_backfill_search_vector'),
    ]

    operations = [
        migrations.RunPython(report_non_kes_gigs, migrations.RunPython.noop),
    ]
