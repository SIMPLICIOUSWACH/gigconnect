import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection

from profiles.models import Skill, SkillAlias

SIMILARITY_THRESHOLD = 0.5


class Command(BaseCommand):
    help = (
        'Report likely duplicate skills. Read-only: it changes nothing. Review the output, then '
        'use `merge_skills <from> <into>` for the ones that really are the same skill.'
    )

    def handle(self, *args, **options):
        skills = list(Skill.objects.all())
        found = False

        by_compact = defaultdict(list)
        for skill in skills:
            by_compact[re.sub(r'[^a-z0-9]', '', skill.normalized_name)].append(skill.name)
        same_letters = [names for names in by_compact.values() if len(names) > 1]
        if same_letters:
            found = True
            self.stdout.write('Same letters and digits, different spelling or spacing:')
            for names in same_letters:
                self.stdout.write('  ' + ' | '.join(sorted(names)))

        skill_keys = {skill.normalized_name: skill.name for skill in skills}
        aliased = [
            (a.alias, skill_keys[a.normalized_alias])
            for a in SkillAlias.objects.all()
            if a.normalized_alias in skill_keys
        ]
        if aliased:
            found = True
            self.stdout.write('Aliases that are also real skills (the real skill wins):')
            for alias, name in aliased:
                self.stdout.write(f'  alias "{alias}" and skill "{name}"')

        table = Skill._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT a.name, b.name, similarity(a.normalized_name, b.normalized_name) AS sim '
                f'FROM {table} a JOIN {table} b ON a.id < b.id '
                f'WHERE similarity(a.normalized_name, b.normalized_name) >= %s ORDER BY sim DESC',
                [SIMILARITY_THRESHOLD],
            )
            similar = cursor.fetchall()
        if similar:
            found = True
            self.stdout.write(f'Similar names (trigram similarity >= {SIMILARITY_THRESHOLD}):')
            for first, second, sim in similar:
                self.stdout.write(f'  {first} | {second}  ({sim:.2f})')

        if not found:
            self.stdout.write('No likely duplicate skills found.')
