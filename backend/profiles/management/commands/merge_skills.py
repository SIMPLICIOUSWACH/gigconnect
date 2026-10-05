import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from profiles.models import FreelancerProfile, Skill, SkillAlias
from profiles.skills import match_key


def _get_skill(ref):
    try:
        uuid.UUID(ref)
        skill = Skill.objects.filter(id=ref).first()
    except ValueError:
        skill = Skill.objects.filter(normalized_name=match_key(ref)).first()
    if skill is None:
        raise CommandError(f'No skill matches "{ref}" (give an exact name or an id; aliases are not accepted).')
    return skill


class Command(BaseCommand):
    help = (
        'Merge a duplicate skill into another: re-point every gig, freelancer profile and alias '
        'that uses <from> to <into>, keep <from>\'s name as an alias of <into>, then delete <from>. '
        'Run duplicates through report_duplicate_skills first; nothing is merged automatically.'
    )

    def add_arguments(self, parser):
        parser.add_argument('from_skill', help='The duplicate to remove (name or id).')
        parser.add_argument('into_skill', help='The skill to keep (name or id).')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without changing it.')

    def handle(self, *args, **options):
        source = _get_skill(options['from_skill'])
        target = _get_skill(options['into_skill'])
        if source.pk == target.pk:
            raise CommandError('<from> and <into> are the same skill.')

        # If a new model ever points at Skill, fail loudly rather than silently orphan it on delete.
        handled = {FreelancerProfile, SkillAlias}
        from gigs.models import Gig, GigSkill

        handled |= {Gig, GigSkill}
        unknown = [
            rel.related_model.__name__ for rel in Skill._meta.related_objects if rel.related_model not in handled
        ]
        if unknown:
            raise CommandError(f'Skill is referenced by models this command does not handle: {unknown}.')

        gig_through = GigSkill
        profile_through = FreelancerProfile.skills.through
        affected_gig_ids = list(gig_through.objects.filter(skill=source).values_list('gig_id', flat=True))

        summary = {
            'gigs': len(affected_gig_ids),
            'freelancer profiles': profile_through.objects.filter(skill_id=source.pk).count(),
            'aliases': SkillAlias.objects.filter(skill=source).count(),
        }
        if options['dry_run']:
            self.stdout.write(f'Would merge "{source.name}" into "{target.name}": {summary}')
            return

        with transaction.atomic():
            # Rows where the target is already present would violate the unique (gig, skill) /
            # (profile, skill) pair, so those are dropped instead of re-pointed.
            gig_through.objects.filter(
                skill=source, gig_id__in=gig_through.objects.filter(skill=target).values('gig_id')
            ).delete()
            gig_through.objects.filter(skill=source).update(skill=target)

            profile_through.objects.filter(
                skill_id=source.pk,
                freelancerprofile_id__in=profile_through.objects.filter(skill_id=target.pk).values(
                    'freelancerprofile_id'
                ),
            ).delete()
            profile_through.objects.filter(skill_id=source.pk).update(skill_id=target.pk)

            SkillAlias.objects.filter(skill=source).update(skill=target)
            source_name = source.name
            source.delete()
            if not Skill.objects.filter(normalized_name=match_key(source_name)).exists():
                SkillAlias.objects.get_or_create(
                    normalized_alias=match_key(source_name), defaults={'alias': source_name, 'skill': target}
                )

            # The bulk updates above bypass m2m_changed, so refresh the affected gigs' search text.
            from gigs.signals import update_search_vector

            for gig in Gig.objects.filter(id__in=affected_gig_ids).prefetch_related('skills'):
                update_search_vector(gig)

        self.stdout.write(self.style.SUCCESS(f'Merged "{source_name}" into "{target.name}": {summary}'))
