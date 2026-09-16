from django.db import migrations

SKILLS = [
    ('Web Development', 'Technology'),
    ('Mobile App Development', 'Technology'),
    ('Graphic Design', 'Design'),
    ('UI/UX Design', 'Design'),
    ('Content Writing', 'Writing'),
    ('Copywriting', 'Writing'),
    ('Social Media Management', 'Marketing'),
    ('Digital Marketing', 'Marketing'),
    ('Photography', 'Media'),
    ('Videography', 'Media'),
    ('Video Editing', 'Media'),
    ('Bookkeeping', 'Business'),
    ('Data Entry', 'Business'),
    ('Virtual Assistance', 'Business'),
    ('Translation', 'Writing'),
    ('Tailoring', 'Trades'),
    ('Plumbing', 'Trades'),
    ('Electrical Work', 'Trades'),
    ('Carpentry', 'Trades'),
    ('Event Planning', 'Business'),
]


def seed_skills(apps, schema_editor):
    Skill = apps.get_model('profiles', 'Skill')
    for name, category in SKILLS:
        Skill.objects.get_or_create(name=name, defaults={'category': category})


def unseed_skills(apps, schema_editor):
    Skill = apps.get_model('profiles', 'Skill')
    Skill.objects.filter(name__in=[name for name, _ in SKILLS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('profiles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_skills, unseed_skills),
    ]
