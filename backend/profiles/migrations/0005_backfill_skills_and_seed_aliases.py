from django.db import migrations

from profiles.skills import match_key

# (canonical skill, category if it has to be created, aliases)
CANONICAL_SKILLS = [
    ('React', 'Technology', ['ReactJS', 'React.js', 'React JS']),
    ('JavaScript', 'Technology', ['JS']),
    ('Python', 'Technology', ['Py', 'Python3']),
    ('Excel', 'Business', ['MS Excel', 'Microsoft Excel']),
]


def backfill_and_seed(apps, schema_editor):
    Skill = apps.get_model('profiles', 'Skill')
    SkillAlias = apps.get_model('profiles', 'SkillAlias')

    for skill in Skill.objects.all():
        skill.normalized_name = match_key(skill.name)
        skill.save(update_fields=['normalized_name'])

    for name, category, aliases in CANONICAL_SKILLS:
        skill = Skill.objects.filter(normalized_name=match_key(name)).first()
        if skill is None:
            skill = Skill.objects.create(name=name, normalized_name=match_key(name), category=category)
        for alias in aliases:
            key = match_key(alias)
            if Skill.objects.filter(normalized_name=key).exists():
                continue  # a real skill already has this name; don't shadow it
            SkillAlias.objects.get_or_create(normalized_alias=key, defaults={'alias': alias, 'skill': skill})


def unseed_aliases(apps, schema_editor):
    SkillAlias = apps.get_model('profiles', 'SkillAlias')
    keys = [match_key(alias) for _, _, aliases in CANONICAL_SKILLS for alias in aliases]
    SkillAlias.objects.filter(normalized_alias__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('profiles', '0004_skill_normalization_and_aliases'),
    ]

    operations = [
        migrations.RunPython(backfill_and_seed, unseed_aliases),
    ]
