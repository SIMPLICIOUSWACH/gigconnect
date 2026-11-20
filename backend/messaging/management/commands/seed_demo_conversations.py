from django.core.management.base import BaseCommand, CommandError

from messaging.demo import DEMO_CLIENT, seed
from recommendations.planted_demo import DemoError


class Command(BaseCommand):
    help = (
        'Planted demo only: a demo client who hired Amina, Brian and Cynthia on three in-progress gigs, with short '
        'sample chats. These rows are flagged is_demo_extra and never used to train or evaluate the recommender. '
        'Running it again replaces the sample chats.'
    )

    def handle(self, *args, **options):
        try:
            conversations = seed()
        except DemoError as error:
            raise CommandError(str(error)) from error
        email, name = DEMO_CLIENT
        self.stdout.write(self.style.SUCCESS(f'{len(conversations)} sample chats for {name} <{email}>:'))
        for conversation in conversations:
            count = conversation.messages.count()
            self.stdout.write(f'  {conversation.freelancer.full_name}: "{conversation.gig.title}", {count} messages')
        self.stdout.write('Sign in as the demo client or as Amina, Brian or Cynthia with the demo password (README).')
