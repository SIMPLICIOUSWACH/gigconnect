"""
The four showcase accounts for live demos, with everything around them filled in.

    Freelancer A  Zawadi Achieng, a designer in Nairobi        Client A  Savanna Brew Café, Nairobi
    Freelancer B  Hassan Mwinyi, a developer in Mombasa        Client B  Pwani Hope Academy, Mombasa

Each freelancer has a full profile, an approved ID check (with a placeholder ID and selfie that say SAMPLE, NOT A REAL
DOCUMENT), four portfolio items, completed gigs with ratings and replies, a hired gig in progress with a chat, one
application in every other status, unread notifications, and open gigs that match their skills so recommendations have
something to show. Each client has gigs in every status.

All of it is flagged is_synthetic and is_demo_extra, so the recommender never trains or is evaluated on it, and it is
hidden wherever synthetic data is hidden. The dates are set from the day of the run; refresh_showcase_dates moves them.
"""

from datetime import timedelta

from django.core.management.base import CommandError

from accounts.models import User
from applications.transitions import Status
from gigs.models import Category, Gig, GigInvite
from profiles.id_privacy import fingerprint_fields
from profiles.models import FreelancerProfile, PortfolioItem, Skill

from . import builders, gigtext, images
from .history import backdate_accounts
from .profiles_fill import sample_users

PASSWORD_PLACEHOLDER = 'dry-run-only-not-saved'
D = timedelta

FREELANCER_A = dict(
    key='freelancer_a', email='showcase-freelancer-a@example.test', name='Zawadi Achieng', phone='+254700000101',
    headline='Brand and social media designer in Nairobi',
    bio='Nairobi designer helping cafés, shops and start-ups look the part. Logos, menus, packaging and a month of '
        'social posts, delivered on time with two rounds of changes included. Most of my work comes from clients who '
        'come back.',
    skills=['Graphic Design', 'Logo Design', 'Social Media Management', 'UI/UX Design', 'Digital Marketing'],
    county='Nairobi', price=3500, colour='coral', id_number='SAMPLE-A-0001',
)
FREELANCER_B = dict(
    key='freelancer_b', email='showcase-freelancer-b@example.test', name='Hassan Mwinyi', phone='+254700000102',
    headline='React and Python developer in Mombasa',
    bio='Mombasa developer building websites, dashboards and small business tools with React and Python. I explain '
        'things in plain language, set up M-Pesa payments and hand over clean code with notes. Schools, hotels and '
        'shops are my regulars.',
    skills=['Web Development', 'React', 'JavaScript', 'Python', 'Mobile App Development'],
    county='Mombasa', price=15000, colour='teal', id_number='SAMPLE-B-0001',
)
CLIENT_A = dict(
    key='client_a', email='showcase-client-a@example.test', name='Wanjiru Kamau', phone='+254700000103',
    company='Savanna Brew Café', industry='hospitality', county='Nairobi',
)
CLIENT_B = dict(
    key='client_b', email='showcase-client-b@example.test', name='Baraka Omondi', phone='+254700000104',
    company='Pwani Hope Academy', industry='education', county='Mombasa',
)
SHOWCASE_EMAILS = [p['email'] for p in (FREELANCER_A, FREELANCER_B, CLIENT_A, CLIENT_B)]

PORTFOLIO = {
    'freelancer_a': [
        ('Savanna Brew Café logo refresh', 'Simplified the old mark, chose new colours and wrote a one-page brand guide for signs, cups and social pages.'),
        ('Lunch menu and table cards', 'A two-sided A4 menu and six matching table cards, delivered print-ready with bleed.'),
        ('Westlands branch opening pack', 'Posters, Instagram posts and a story template for a branch launch, all in one visual style.'),
        ('Honey jar labels', 'A label set for three jar sizes with an ingredients panel and a barcode space.'),
    ],
    'freelancer_b': [
        ('Fee tracker for a primary school', 'A dashboard showing who has paid and who owes, with printable receipts and monthly totals.'),
        ('Booking site for a Diani guesthouse', 'A fast, mobile-friendly site with room details and a booking form that emails the owner.'),
        ('Inventory app for a hardware shop', 'Stock in, stock out and low-stock alerts, usable on a phone at the counter.'),
        ('Parents portal with results and notices', 'A login for parents to see results, fee balances and school notices on their phones.'),
    ],
}

# Handwritten completed gigs. who: 'client' (the showcase client) or an index into the sample clients.
# (hired days ago, who, title, description, skills, budget, rating, review, reply)
COMPLETED_A = [
    (300, 0, 'Flyers for a salon opening', 'Two A5 flyer designs for a salon opening, with our logo and a map.', ['Graphic Design'], (4000, 6000), None, '', ''),
    (270, 'client', 'Logo refresh for Savanna Brew Café', 'Our old logo is tired. We want a cleaner mark and a simple brand guide so the signboard, cups and website match.', ['Logo Design', 'Graphic Design'], (12000, 15000), 5,
     'Zawadi took our tired old logo and gave us something we are proud to put on the signboard. She sent three options in two days and the final files covered everything from cups to the website. Customers have commented on it.',
     'Wanjiru and the team were a joy to work with. Thank you for trusting me with the café look.'),
    (235, 1, 'Brand colours and logo for a tailoring shop', 'A logo and a colour palette for a small tailoring shop, to use on the sign and garment labels.', ['Logo Design', 'Graphic Design'], (8000, 11000), 5,
     'Very patient with my many small changes. The logo now sits on our shop sign and on every garment label.', 'Thank you! The shop looks lovely.'),
    (205, 'client', 'Menu design for the new lunch range', 'A clear two-sided lunch menu and matching table cards, print-ready for our local printer.', ['Graphic Design'], (8000, 12000), 5,
     'Our lunch menu is finally easy to read and the table cards match. Everything was print-ready and arrived a day early.', ''),
    (175, 2, 'Instagram templates for a bakery', 'Six editable post templates the bakery can reuse every week.', ['Social Media Management', 'Graphic Design'], (6000, 9000), 5,
     'Six templates that we reuse every week. Simple to edit even for a non-designer like me.', ''),
    (150, 3, 'Wedding stationery set', 'Invitations, programmes and thank-you cards for a wedding of 200 guests.', ['Graphic Design'], (10000, 14000), 4,
     'Beautiful invitations and programmes. Two corrections to the spelling of names took a day to sort, otherwise great.', ''),
    (120, 'client', 'Social media pack for the Westlands branch opening', 'Posters, Instagram posts and a story template for the opening weekend of our second branch.', ['Social Media Management', 'Digital Marketing', 'Graphic Design'], (18000, 25000), 4,
     'A full launch pack of posters and posts. The opening weekend was busy and people mentioned the Instagram posts. Only note is that some captions needed trimming.', ''),
    (70, 4, 'Posters for a community clean-up', 'Three posters for a neighbourhood clean-up day, in English and Kiswahili.', ['Graphic Design'], (3000, 5000), 5,
     'Quick, kind and exactly on brief. The posters were all over town within two days.', 'Happy to support the cause!'),
]
COMPLETED_B = [
    (280, 5, 'Customer database clean-up script', 'Merge duplicates and fix formatting across several customer spreadsheets, with a script we can repeat.', ['Python'], (18000, 25000), None, '', ''),
    (230, 'client', 'Fee payment tracker for the accounts office', 'A simple system to record fee payments, show balances per class and print receipts.', ['Python', 'JavaScript', 'Web Development'], (45000, 60000), 5,
     'Hassan built exactly what our accounts office needed. Parents payments are now recorded the same day and the receipts print properly. He trained two staff members and left clear notes.',
     'Thank you. Glad the office is running smoothly.'),
    (180, 6, 'Booking site for a guesthouse in Diani', 'A mobile-friendly site with rooms, photos and a booking request form that emails us.', ['Web Development', 'JavaScript'], (40000, 55000), 5,
     'Our booking requests now arrive by email and bookings are up since the site went live. Works well on phones.', ''),
    (130, 7, 'Inventory app for a hardware shop', 'An app for stock in, stock out and low-stock alerts at the counter.', ['JavaScript', 'Mobile App Development'], (30000, 40000), 3,
     'The app works and the stock counts are accurate now, but it was delivered two weeks after the date we agreed and I had to chase for updates.',
     'Thank you for the honest feedback, and apologies for the delay. I underestimated the barcode part and should have told you earlier. I now share a short weekly progress note on every job.'),
    (75, 'client', 'Parents portal for results and notices', 'A login for parents to see results, fee balances and notices on their phones.', ['React', 'JavaScript', 'Web Development'], (55000, 70000), 5,
     'Parents can now see results and notices from their phones. Hassan was calm during the term-start rush and fixed the issues the same day.', 'Thank you. It was a good project to be part of.'),
]

CHAT_A = [
    ('client', 'Hi Zawadi, thanks for taking this on. Here is the brief: a seasonal menu for December plus six table tent cards. The photos are in the shared folder.'),
    ('freelancer', 'Thank you, Wanjiru. I have the folder. Do you want to keep the current colours or try the new green from the logo refresh?'),
    ('client', 'Let us use the new green with the cream background. Prices are final except the cold brew, which I will confirm on Monday.'),
    ('freelancer', 'Perfect. I will send a first draft of the menu on Wednesday and the tent cards on Friday.'),
    ('client', 'That works. Our printer needs the files by the 14th, so there is a little room.'),
    ('freelancer', 'Noted. I will export in A4 and A5 with bleed so the printer has no surprises.'),
    ('client', 'Brilliant. A deposit of 5,000 has gone through M-Pesa, please confirm when you see it.'),
    ('freelancer', 'Received, thank you. Draft one is attached. Kindly check the cold brew line when you have the price.'),
    ('client', 'Looks great! Cold brew is 350. Could the tent cards say "Ask about our coffee subscription"?'),
]
CHAT_B = [
    ('client', 'Good morning Hassan. Thank you for taking on the open day page. Parents should be able to pick a time slot and register their child.'),
    ('freelancer', 'Good morning Baraka. Understood. How many slots per day, and do you need a confirmation SMS or only email?'),
    ('client', 'Six slots a day for five days, thirty in all. Email is fine for now. SMS can wait until after the open day.'),
    ('freelancer', 'Great. I will build the slot picker first and share a test link on Thursday.'),
    ('client', "Please also add a field for the child's current school."),
    ('freelancer', 'Added to the plan. I will make sure the form works well on a phone, since most parents will open it from WhatsApp.'),
    ('client', 'Yes please. Our head teacher would like to see the test link before it goes out.'),
    ('freelancer', 'Of course. The test link is ready on the staging site I sent earlier. Let me know what the head teacher thinks.'),
    ('client', 'Opened it on my phone and it works well. The head teacher is happy with the layout.'),
]

# Open gigs from the sample clients, picked from the gig banks so the freelancers have real matches to be shown.
# (group, bank index, skills) for gigs nobody has applied to yet, then (group, index, skills, status of the freelancer's application).
MARKET_A_OPEN = [
    ('design', 0, ['Logo Design', 'Graphic Design']), ('design', 3, ['Graphic Design', 'Logo Design']),
    ('design', 5, ['Social Media Management', 'Graphic Design']), ('design', 6, ['Graphic Design']),
    ('marketing', 2, ['Social Media Management', 'Digital Marketing']), ('marketing', 4, ['Digital Marketing']),
]
MARKET_A_APPLIED = [
    ('marketing', 0, ['Social Media Management', 'Digital Marketing'], 'pending'),
    ('design', 1, ['Graphic Design'], 'under_review'),
    ('design', 2, ['Graphic Design'], 'withdrawn'),
]
MARKET_A_CLOSED = ('design', 8, ['Graphic Design', 'Logo Design'], 'rejected')
MARKET_B_OPEN = [
    ('tech', 0, ['Web Development', 'JavaScript']), ('tech', 1, ['Web Development', 'JavaScript', 'React']),
    ('tech', 3, ['Python', 'Web Development']), ('tech', 6, ['React', 'JavaScript']), ('tech', 7, ['Python', 'JavaScript']),
]
MARKET_B_APPLIED = [
    ('tech', 2, ['Web Development', 'JavaScript'], 'pending'),
    ('tech', 4, ['Mobile App Development', 'JavaScript'], 'under_review'),
    ('tech', 9, ['Python'], 'withdrawn'),
]
MARKET_B_CLOSED = ('tech', 5, ['Web Development', 'JavaScript'], 'rejected')
PATHS = {
    'pending': [], 'under_review': [Status.UNDER_REVIEW], 'shortlisted': [Status.UNDER_REVIEW, Status.SHORTLISTED],
    'rejected': [Status.UNDER_REVIEW, Status.REJECTED], 'withdrawn': [Status.WITHDRAWN],
}


class Showcase:
    def __init__(self, ctx, password):
        self.ctx, self.password = ctx, password
        self.rng = ctx.rng('showcase')
        self.now = ctx.now
        self.skills = {s.name: s for s in Skill.objects.all()}
        self.categories = {c.name: c for c in Category.objects.all()}
        self.sample_clients = list(sample_users(User.Role.CLIENT))
        self.sample_freelancers = list(sample_users(User.Role.FREELANCER))
        if not self.sample_clients or len(self.sample_freelancers) < 4:
            raise CommandError('There are no sample accounts to build around. Run seed_data first.')
        self.people = {}
        self.gigs = {}

    # -- small helpers ------------------------------------------------------------------------------------------------

    def ago(self, days):
        return self.now - D(days=days)

    def client_pool(self, index):
        return self.sample_clients[index % len(self.sample_clients)]

    def skill_objects(self, names):
        missing = [n for n in names if n not in self.skills]
        if missing:
            raise CommandError(f'These skills are missing from the catalogue: {", ".join(missing)}.')
        return [self.skills[n] for n in names]

    def category_for(self, skill_names):
        from .text import GROUP_CATEGORY, SKILL_GROUP
        return self.categories[GROUP_CATEGORY[SKILL_GROUP[skill_names[0]]]]

    def applicants(self, groups, count, start):
        """Sample freelancers to fill out a client's open gigs, favouring the right kind of work."""
        from .profiles_fill import group_of
        fitting = [f for f in self.sample_freelancers
                   if group_of([s.name for s in f.freelancer_profile.skills.all()]) in groups]
        pool = fitting + [f for f in self.sample_freelancers if f not in fitting]
        return [pool[(start + n) % len(pool)] for n in range(count)]

    # -- people -------------------------------------------------------------------------------------------------------

    def make_user(self, spec, role):
        user = User.objects.create_user(
            email=spec['email'], password=self.password, full_name=spec['name'], phone=spec['phone'], role=role,
            is_email_verified=True, is_profile_complete=True, is_synthetic=True, is_demo_extra=True,
        )
        self.ctx.ledger.created(user)
        self.ctx.count('accounts')
        self.people[spec['key']] = user
        return user

    def make_freelancer(self, spec):
        ctx = self.ctx
        user = self.make_user(spec, User.Role.FREELANCER)
        profile = user.freelancer_profile
        profile.headline, profile.bio, profile.county = spec['headline'], spec['bio'], spec['county']
        profile.starting_price, profile.is_available, profile.open_to_remote = spec['price'], True, True
        profile.profile_colour = spec['colour']
        ctx.save_image(profile.profile_photo, f'showcase-avatar-{spec["key"]}.png', images.avatar(spec['name'], spec['colour']))
        profile.save()
        profile.skills.set(self.skill_objects(spec['skills']))
        for position, (title, description) in enumerate(PORTFOLIO[spec['key']]):
            item = PortfolioItem.objects.create(freelancer=profile, title=title, description=description)
            PortfolioItem.objects.filter(pk=item.pk).update(created_at=self.ago(20 + position * 9))
            ctx.ledger.created(item)
            ctx.save_image(item.image, f'showcase-cover-{item.pk.hex[:8]}.png', images.cover(title, spec['colour'], position))
            item.save(update_fields=['image'])
            ctx.count('portfolio items')
        self.verify(profile, spec)
        return user

    def verify(self, profile, spec):
        """An approved ID check, with placeholder pictures that say they are samples. No real document or face."""
        ctx = self.ctx
        submitted = self.ago(45)
        profile.id_number = spec['id_number']
        for name, value in fingerprint_fields(spec['id_number']).items():
            setattr(profile, name, value)
        ctx.save_image(profile.id_document, f'showcase-id-{spec["key"]}.png', images.id_card())
        ctx.save_image(profile.selfie, f'showcase-selfie-{spec["key"]}.png', images.selfie())
        profile.verification_status = FreelancerProfile.VerificationStatus.VERIFIED
        profile.verification_submitted_at = submitted
        profile.selfie_challenge = 'Hold up two fingers next to your face'
        profile.selfie_challenge_issued_at = submitted - D(minutes=4)
        profile.selfie_consent_at = submitted - D(minutes=3)
        profile.selfie_submitted_at = submitted
        profile.face_match_score = None
        profile.face_match_model = 'sample placeholder, no real check was run'
        profile.verification_decided_at = self.ago(43)
        profile.needs_new_id = profile.needs_new_selfie = False
        profile.save()
        ctx.count('approved ID checks')

    def make_client(self, spec):
        ctx = self.ctx
        user = self.make_user(spec, User.Role.CLIENT)
        profile = user.client_profile
        profile.company_name, profile.industry = spec['company'], spec['industry']
        colour = images.colour_for(spec['company'])
        ctx.save_image(profile.company_logo, f'showcase-logo-{spec["key"]}.png', images.logo(spec['company'], colour))
        profile.save()
        return user

    # -- gigs ---------------------------------------------------------------------------------------------------------

    def gig(self, client, title, description, skill_names, status, posted, window, delivery, budget, county,
            changed_at=None, remote=False):
        return builders.create_gig(
            self.ctx, client=client, category=self.category_for(skill_names), title=title, description=description,
            skills=self.skill_objects(skill_names), status=status, posted_at=posted, window_days=window,
            delivery_days=delivery, budget=budget, county=county, is_remote=remote, changed_at=changed_at,
        )

    def letter(self, skill_names, biz):
        return self.rng.choice(gigtext.LETTERS).format(skill=skill_names[0], biz=biz)

    def completed(self, freelancer, client_spec, row):
        ctx = self.ctx
        hired_ago, who, title, description, skill_names, budget, rating, review, reply = row
        client = self.people[client_spec['key']] if who == 'client' else self.client_pool(who)
        hired = self.ago(hired_ago)
        shortlisted, reviewed, applied = hired - D(days=1.1), hired - D(days=2.2), hired - D(days=3.3)
        posted, completed = applied - D(days=2.5), hired + D(days=14)
        gig = self.gig(
            client, title, description, skill_names, Gig.Status.COMPLETED, posted, 7,
            (completed - posted).days + 2, budget, client_spec['county'] if who == 'client' else None,
            changed_at=completed,
        )
        application = builders.add_application(
            ctx, gig, freelancer, applied,
            [(Status.UNDER_REVIEW, reviewed), (Status.SHORTLISTED, shortlisted), (Status.HIRED, hired)],
            cover_letter=self.letter(skill_names, client.client_profile.company_name or client.full_name),
            proposed_rate=builders.round_to(budget[1] * 0.92),
        )
        builders.open_conversation(ctx, application, hired)
        if rating:
            written = completed + D(days=1.2)
            builders.add_review(ctx, gig, freelancer, rating, review, written, reply, written + D(days=1.5))
        return gig, application

    def in_progress(self, freelancer, client, title, description, skill_names, hired_ago, delivery_in, budget, chat,
                    county):
        ctx = self.ctx
        hired = self.ago(hired_ago)
        shortlisted, reviewed, applied = hired - D(days=1.1), hired - D(days=2.2), hired - D(days=3.3)
        posted = applied - D(days=2.5)
        gig = self.gig(
            client, title, description, skill_names, Gig.Status.IN_PROGRESS, posted, 7,
            (self.now - posted).days + delivery_in, budget, county, changed_at=hired,
        )
        application = builders.add_application(
            ctx, gig, freelancer, applied,
            [(Status.UNDER_REVIEW, reviewed), (Status.SHORTLISTED, shortlisted), (Status.HIRED, hired)],
            cover_letter=self.letter(skill_names, client.client_profile.company_name),
        )
        conversation = builders.open_conversation(ctx, application, hired)
        builders.write_messages(ctx, conversation, chat, hired + D(hours=1), unread_from=len(chat) - 1)
        return gig, application, conversation

    def apply_with(self, gig, freelancer, path, applied, biz, skill_names):
        steps, when = [], applied
        for status in PATHS[path]:
            when = when + D(days=1.1)
            steps.append((status, when))
        return builders.add_application(
            self.ctx, gig, freelancer, applied, steps, cover_letter=self.letter(skill_names, biz),
        )

    def open_gig(self, client, spec, title, description, skill_names, posted_days_ago, left, applicants):
        """An open gig for a showcase client. applicants: [(freelancer, path, applied days ago)]."""
        gig = self.gig(
            client, title, description, skill_names, Gig.Status.OPEN, self.ago(posted_days_ago),
            posted_days_ago + left, posted_days_ago + left + 21, (10000, 20000), spec['county'],
        )
        for freelancer, path, applied_ago in applicants:
            self.apply_with(gig, freelancer, path, self.ago(applied_ago), spec['company'], skill_names)
        return gig

    def closed_gig(self, client, spec, title, description, skill_names, posted_days_ago, applicant, path):
        posted = self.ago(posted_days_ago)
        gig = self.gig(
            client, title, description, skill_names, Gig.Status.CLOSED, posted, 10, 30, (5000, 9000), spec['county'],
            changed_at=posted + D(days=14),
        )
        self.apply_with(gig, applicant, path, posted + D(days=2), spec['company'], skill_names)
        return gig

    def market_gig(self, index, group, bank_index, skill_names, status, freelancer_path=None, freelancer=None,
                   posted_ago=6, left=24):
        """A gig from a sample client, taken from the gig banks."""
        title, description = gigtext.GIGS[group][bank_index]
        client = self.client_pool(index)
        biz = client.client_profile.company_name or client.full_name
        title, description = title.format(biz=biz), description.format(biz=biz)
        county = 'Mombasa' if group == 'tech' else 'Nairobi'
        if status == Gig.Status.OPEN:
            gig = self.gig(client, title, description, skill_names, status, self.ago(posted_ago), posted_ago + left,
                           posted_ago + left + 30, (8000, 24000) if group != 'tech' else (30000, 70000), county,
                           remote=index % 2 == 0)
        else:
            posted = self.ago(posted_ago)
            gig = self.gig(client, title, description, skill_names, status, posted, 12, 35, (6000, 14000), county,
                           changed_at=posted + D(days=18))
        if freelancer_path:
            applied = self.ago(posted_ago - 1.0 if status == Gig.Status.OPEN else posted_ago - 2)
            self.apply_with(gig, freelancer, freelancer_path, applied, biz, skill_names)
        return gig

    def market(self, freelancer, open_rows, applied_rows, closed_row, offset):
        index, opened = offset, []
        for group, bank_index, skill_names in open_rows:
            opened.append(self.market_gig(
                index, group, bank_index, skill_names, Gig.Status.OPEN, posted_ago=3 + index % 5, left=14 + index % 20,
            ))
            index += 1
        for group, bank_index, skill_names, path in applied_rows:
            self.market_gig(index, group, bank_index, skill_names, Gig.Status.OPEN, path, freelancer,
                            posted_ago=9 + index % 4, left=20 + index % 10)
            index += 1
        group, bank_index, skill_names, path = closed_row
        self.market_gig(index, group, bank_index, skill_names, Gig.Status.CLOSED, path, freelancer, posted_ago=90)
        self.ctx.count('matching open gigs', len(open_rows))
        return opened

    # -- notifications -------------------------------------------------------------------------------------------------

    def note(self, recipient, kind, title, body, link, days_ago, read=False):
        return builders.add_notification(self.ctx, recipient, kind, title, body, link, self.ago(days_ago), read)

    # -- the whole thing ----------------------------------------------------------------------------------------------

    def build(self):
        ctx = self.ctx
        a, b = self.make_freelancer(FREELANCER_A), self.make_freelancer(FREELANCER_B)
        ca, cb = self.make_client(CLIENT_A), self.make_client(CLIENT_B)

        for row in COMPLETED_A:
            self.completed(a, CLIENT_A, row)
        for row in COMPLETED_B:
            self.completed(b, CLIENT_B, row)

        _, _, chat_a = self.in_progress(
            a, ca, 'Seasonal menu and table tent cards', 'A festive December menu and six table tent cards in the new brand green. Files for our printer by the 14th.',
            ['Graphic Design'], 9, 9, (10000, 14000), CHAT_A, CLIENT_A['county'],
        )
        _, _, chat_b = self.in_progress(
            b, cb, 'Open day booking and registration page', 'A page where parents choose a time slot and register their child for the open day. Must work well on phones.',
            ['React', 'Web Development', 'JavaScript'], 12, 14, (40000, 55000), CHAT_B, CLIENT_B['county'],
        )

        helpers = self.applicants({'design', 'marketing'}, 6, 0)
        ca5 = self.open_gig(
            ca, CLIENT_A, 'Instagram content for the coffee subscription launch',
            'We are launching a monthly coffee subscription and need a month of Instagram posts and stories that explain it clearly.',
            ['Social Media Management', 'Digital Marketing', 'Graphic Design'], 8, 21,
            [(a, 'shortlisted', 6.5), (helpers[0], 'pending', 4), (helpers[1], 'under_review', 6), (helpers[2], 'rejected', 7)],
        )
        ca6 = self.open_gig(
            ca, CLIENT_A, 'Packaging labels for our house blend coffee bags',
            'Label artwork for 250g and 1kg bags of our house blend. We have the logo and the brand colours.',
            ['Graphic Design', 'Logo Design'], 4, 30, [(helpers[3], 'pending', 3), (helpers[4], 'under_review', 3.5)],
        )
        self.closed_gig(
            ca, CLIENT_A, 'Poster for cinema night', 'A poster for a one-off cinema night in the café. We found someone locally in the end.',
            ['Graphic Design'], 100, helpers[5], 'rejected',
        )
        devs = self.applicants({'tech'}, 3, 0)
        cb4 = self.open_gig(
            cb, CLIENT_B, 'Mobile-friendly refresh of the school website',
            'Our school website is slow and hard to use on phones. We need the main pages redesigned and the news section easier to update.',
            ['Web Development', 'React', 'JavaScript'], 10, 18,
            [(b, 'shortlisted', 9), (devs[0], 'pending', 5), (devs[1], 'under_review', 8), (devs[2], 'rejected', 9)],
        )
        self.closed_gig(
            cb, CLIENT_B, 'Library catalogue spreadsheet', 'A spreadsheet to catalogue our library books. We settled on a paper system.',
            ['Python'], 120, devs[0], 'rejected',
        )

        match_a = self.market(a, MARKET_A_OPEN, MARKET_A_APPLIED, MARKET_A_CLOSED, offset=0)[0]
        match_b = self.market(b, MARKET_B_OPEN, MARKET_B_APPLIED, MARKET_B_CLOSED, offset=11)[0]

        invite = GigInvite.objects.create(gig=ca6, client=ca, freelancer=a)
        GigInvite.objects.filter(pk=invite.pk).update(created_at=self.ago(2))
        ctx.count('invites')

        self.notifications(a, b, ca, cb, ca5, ca6, cb4, match_a, match_b, chat_a, chat_b)
        for freelancer in (a, b):
            from reviews.service import refresh_rating
            refresh_rating(freelancer)
        for user in (a, b, ca, cb):
            ctx.touch(user, self.ago(330))
        self.created_ids = {user.pk for user in self.people.values()}
        backdate_accounts(ctx)
        # The showcase accounts are new rows: give them their own join dates rather than recording an old value.
        for user in self.people.values():
            User.objects.filter(pk=user.pk).update(created_at=self.ago(345 + self.rng.randint(0, 10)))
        return self.people

    def notifications(self, a, b, ca, cb, ca5, ca6, cb4, match_a, match_b, chat_a, chat_b):
        app_a = ca5.applications.get(freelancer=a)
        app_b = cb4.applications.get(freelancer=b)
        self.note(a, 'application_status', 'Application shortlisted', 'Savanna Brew Café shortlisted your application for "Instagram content for the coffee subscription launch".', f'/applications/{app_a.pk}', 3)
        self.note(a, 'gig_invite', 'Invitation to apply', 'Savanna Brew Café invited you to apply for "Packaging labels for our house blend coffee bags".', f'/gigs/{ca6.pk}', 2)
        self.note(a, 'new_message', 'New message from Savanna Brew Café', CHAT_A[-1][1], f'/messages/{chat_a.pk}', 0.4)
        self.note(a, 'new_gig_match', 'New gig match', f'A new gig matches your skills: "{match_a.title}".', f'/gigs/{match_a.pk}', 1)
        self.note(a, 'review_received', 'Savanna Brew Café rated your work', 'You received a 4-star rating for "Social media pack for the Westlands branch opening".', f'/profile/{a.pk}', 118, read=True)
        self.note(b, 'application_status', 'Application shortlisted', 'Pwani Hope Academy shortlisted your application for "Mobile-friendly refresh of the school website".', f'/applications/{app_b.pk}', 5)
        self.note(b, 'new_message', 'New message from Pwani Hope Academy', CHAT_B[-1][1], f'/messages/{chat_b.pk}', 0.3)
        self.note(b, 'new_gig_match', 'New gig match', f'A new gig matches your skills: "{match_b.title}".', f'/gigs/{match_b.pk}', 1)
        self.note(b, 'review_received', 'Pwani Hope Academy rated your work', 'You received a 5-star rating for "Parents portal for results and notices".', f'/profile/{b.pk}', 73, read=True)
        for recipient, gig, spec_days in ((ca, ca5, (4, 6, 7)), (cb, cb4, (5, 8, 9))):
            for application, days in list(zip(gig.applications.exclude(freelancer__in=[a, b]), spec_days))[:2]:
                self.note(recipient, 'new_application', 'New application', f'{application.freelancer.full_name} applied for "{gig.title}".', f'/gigs/{gig.pk}/applicants', days - 3.5)
        self.note(ca, 'review_reply', 'Zawadi replied to your review', 'Zawadi Achieng replied to your review of "Logo refresh for Savanna Brew Café".', f'/profile/{a.pk}', 260, read=True)
        self.note(cb, 'review_reply', 'Hassan replied to your review', 'Hassan Mwinyi replied to your review of "Parents portal for results and notices".', f'/profile/{b.pk}', 58, read=True)


def seed_showcase(ctx, password):
    return Showcase(ctx, password).build()
