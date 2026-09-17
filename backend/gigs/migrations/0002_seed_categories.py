from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    'Web & Software Development',
    'Design & Creative',
    'Marketing & Sales',
    'Writing & Content',
    'Admin & Virtual Assistance',
    'Data & Analytics',
    'Video & Photography',
    'Local Services',
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('gigs', 'Category')
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={'slug': slugify(name)})


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('gigs', 'Category')
    Category.objects.filter(name__in=CATEGORIES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('gigs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
