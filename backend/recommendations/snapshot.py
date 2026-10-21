"""
A copy of exactly which GigConnect data a training run used, written to datasets/platform/ so it can be
opened and checked.

This is real user data, so it is gitignored and never leaves the machine, and it holds as little as it can:
ids, skills, interaction types and times. No names, emails, phone numbers, bios or cover letters.
"""

import csv
from pathlib import Path

from django.conf import settings

from .features import gig_document

GIG_COLUMNS = ['gig_id', 'category', 'title', 'skills', 'status', 'is_synthetic', 'created_at']
FREELANCER_COLUMNS = ['freelancer_id', 'skills', 'is_synthetic']
INTERACTION_COLUMNS = ['freelancer_id', 'gig_id', 'type', 'weight', 'is_synthetic', 'created_at']
APPLICATION_COLUMNS = ['freelancer_id', 'gig_id', 'status', 'weight', 'is_synthetic', 'created_at']


def _write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def gig_rows(gigs):
    return [
        {
            'gig_id': gig.id,
            'category': gig.category.name,
            'title': gig.title,
            'skills': ';'.join(sorted(skill.name for skill in gig.skills.all())),
            'status': gig.status,
            'is_synthetic': gig.is_synthetic,
            'created_at': gig.created_at.isoformat(),
        }
        for gig in gigs
    ]


def freelancer_rows(profiles):
    # Skills only. The free-text bio can hold personal details, so it is deliberately not copied.
    return [
        {
            'freelancer_id': profile.user_id,
            'skills': ';'.join(sorted(skill.name for skill in profile.skills.all())),
            'is_synthetic': profile.user.is_synthetic,
        }
        for profile in profiles
    ]


def interaction_rows(interactions):
    weights = settings.RECOMMENDER_INTERACTION_WEIGHTS
    return [
        {
            'freelancer_id': interaction.user_id,
            'gig_id': interaction.gig_id,
            'type': interaction.type,
            'weight': weights.get(interaction.type, ''),
            'is_synthetic': interaction.is_synthetic or interaction.user.is_synthetic,
            'created_at': interaction.created_at.isoformat(),
        }
        for interaction in interactions.select_related('user')
    ]


def application_rows(applications):
    # The status only. The cover letter, link and rate are never copied.
    weights = settings.RECOMMENDER_APPLICATION_WEIGHTS
    return [
        {
            'freelancer_id': application.freelancer_id,
            'gig_id': application.gig_id,
            'status': application.status,
            'weight': weights.get(application.status, ''),
            'is_synthetic': application.is_synthetic or application.freelancer.is_synthetic,
            'created_at': application.created_at.isoformat(),
        }
        for application in applications.select_related('freelancer')
    ]


def write_snapshot(data_dir, gigs, profiles, interactions, applications):
    """Write the four CSV files and return how many rows each has."""
    folder = Path(data_dir) / 'platform'
    return {
        'gigs': _write(folder / 'gigs.csv', GIG_COLUMNS, gig_rows(gigs)),
        'freelancers': _write(folder / 'freelancers.csv', FREELANCER_COLUMNS, freelancer_rows(profiles)),
        'interactions': _write(folder / 'interactions.csv', INTERACTION_COLUMNS, interaction_rows(interactions)),
        'applications': _write(folder / 'applications.csv', APPLICATION_COLUMNS, application_rows(applications)),
    }


def platform_documents(gigs):
    """The cleaned document for each gig, alongside whether the gig is synthetic."""
    documents = []
    for gig in gigs:
        skills = [skill.name for skill in gig.skills.all()]
        documents.append({
            'gig_id': gig.id,
            'is_synthetic': gig.is_synthetic,
            'clean_text': gig_document(gig.title, gig.description, skills, gig.category.name),
        })
    return documents
