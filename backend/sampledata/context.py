import random
from collections import Counter
from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.utils import timezone

from .ledger import Ledger


@dataclass
class Context:
    """What one run of a command carries around: the batch it belongs to, its dice, its clock and its tally."""

    batch: str
    seed: int
    dry_run: bool = False
    now: object = field(default_factory=timezone.now)
    stats: Counter = field(default_factory=Counter)
    saved_files: list = field(default_factory=list)
    earliest: dict = field(default_factory=dict)  # {user: the first date their sample history reaches back to}

    def __post_init__(self):
        self.ledger = Ledger(self.batch)

    def rng(self, *parts):
        """Dice that depend only on the seed and what they are for, so a rerun makes the same choices."""
        return random.Random(':'.join([str(self.seed), *map(str, parts)]))

    def count(self, what, number=1):
        self.stats[what] += number

    def touch(self, user, when):
        """Note that this account takes part in something dated `when`, so its join date can be made earlier."""
        if user not in self.earliest or when < self.earliest[user]:
            self.earliest[user] = when

    def save_image(self, file_field, name, data):
        """Save generated picture bytes into an image field. A dry run only counts it."""
        self.count('images')
        if self.dry_run:
            return
        file_field.save(name, ContentFile(data), save=False)
        self.saved_files.append((file_field.storage, file_field.name))
