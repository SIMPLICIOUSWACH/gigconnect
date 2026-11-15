"""
The wording behind the sample data, in Kenyan English, grouped by kind of work. All of it is invented. Banks are
long enough that two freelancers rarely share a line, and the commands pick without repeating where they can.
"""

# Which group of work each skill belongs to, and the gig category a group's work is posted in.
SKILL_GROUP = {
    'Graphic Design': 'design', 'UI/UX Design': 'design', 'Logo Design': 'design',
    'Digital Marketing': 'marketing', 'Social Media Management': 'marketing',
    'Photography': 'media', 'Video Editing': 'media', 'Videography': 'media',
    'JavaScript': 'tech', 'Mobile App Development': 'tech', 'Python': 'tech', 'React': 'tech', 'Web Development': 'tech',
    'Content Writing': 'writing', 'Copywriting': 'writing', 'Translation': 'writing',
    'Bookkeeping': 'business', 'Data Entry': 'business', 'Event Planning': 'business', 'Excel': 'business',
    'Virtual Assistance': 'business',
    'Carpentry': 'trades', 'Electrical Work': 'trades', 'Plumbing': 'trades', 'Tailoring': 'trades',
}
GROUP_CATEGORY = {
    'design': 'Design & Creative', 'marketing': 'Marketing & Sales', 'media': 'Video & Photography',
    'tech': 'Web & Software Development', 'writing': 'Writing & Content', 'business': 'Admin & Virtual Assistance',
    'trades': 'Local Services',
}
# Bookkeeping and Excel work is posted as data work.
SKILL_CATEGORY_OVERRIDE = {'Excel': 'Data & Analytics', 'Bookkeeping': 'Data & Analytics'}

# KES, what one gig of this kind usually costs: (smallest, largest) for the budget, and the freelancer's "from" price.
BUDGET_RANGE = {
    'design': (3000, 28000), 'marketing': (5000, 45000), 'media': (8000, 65000), 'tech': (15000, 120000),
    'writing': (2000, 22000), 'business': (3000, 30000), 'trades': (2500, 40000),
}
STARTING_PRICE_RANGE = {
    'design': (2000, 6000), 'marketing': (3000, 8000), 'media': (5000, 15000), 'tech': (8000, 30000),
    'writing': (1000, 4000), 'business': (1500, 5000), 'trades': (1500, 8000),
}

# Where sample freelancers are based. Nairobi and Mombasa come up more often, as they would.
COUNTY_WEIGHTS = {
    'Nairobi': 8, 'Mombasa': 4, 'Kisumu': 3, 'Nakuru': 3, 'Uasin Gishu': 2, 'Kiambu': 3, 'Machakos': 2,
    'Kakamega': 1, 'Nyeri': 1, 'Kajiado': 1, 'Meru': 1, 'Kilifi': 1,
}

HEADLINES = {
    'design': ['Logo and brand designer based in {county}', 'Graphic designer for shops, cafés and start-ups',
               'Designer for logos, flyers and social media graphics'],
    'marketing': ['Social media and marketing help for small businesses', 'Digital marketer based in {county}',
                  'I run social pages and small ad campaigns for local shops'],
    'media': ['Photographer and video editor in {county}', 'Event and product photography, with edits included',
              'Short videos and reels for businesses and events'],
    'tech': ['Web and app developer based in {county}', 'I build websites and small business tools',
             'Developer for websites, dashboards and mobile apps'],
    'writing': ['Writer for websites, brochures and blogs', 'Copywriter and editor in {county}',
                'Clear, friendly writing in English and Kiswahili'],
    'business': ['Virtual assistant and data entry support', 'Bookkeeping and spreadsheets for small businesses',
                 'Reliable admin help, from inboxes to event schedules'],
    'trades': ['Skilled hands for repairs and fittings in {county}', 'Local tradesperson, quotes within a day',
               'Tailoring, carpentry and fixing jobs done neatly'],
}

# (title, description) pairs for portfolio items, by group. The cover image is drawn from the title.
PORTFOLIO = {
    'design': [
        ('Logo and brand kit for a tailoring shop', 'Main and small logos, a colour palette and a one-page brand guide.'),
        ('Menu design for a Westlands café', 'A two-sided A4 menu and matching table cards, ready for the printer.'),
        ('Launch poster series', 'Three posters for a salon opening, sized for print and for Instagram.'),
        ('Product labels for a honey seller', 'Label set for three jar sizes, with a barcode box and ingredients panel.'),
        ('App icon and onboarding screens', 'An icon and four onboarding screens for a small delivery app.'),
    ],
    'marketing': [
        ('Four-week social media plan', 'Content calendar, captions and posting times for a hardware shop.'),
        ('Facebook ads for a new gym', 'Three ad sets and a small budget plan that brought in 40 sign-up calls.'),
        ('Instagram refresh for a bakery', 'New grid layout, highlights and a weekly posting routine.'),
        ('WhatsApp catalogue for a clothing shop', 'Product photos arranged into a catalogue and a broadcast schedule.'),
        ('Campaign report for a school open day', 'What was posted, what worked, and what to repeat next term.'),
    ],
    'media': [
        ('Wedding highlights reel', 'A four-minute edit with music and titles, delivered in two formats.'),
        ('Product shots for an online shop', 'Forty clean photos on white and in-use, retouched and sized for the website.'),
        ('Restaurant promo video', 'Ninety seconds of filming and editing for a Nyali seafood place.'),
        ('Conference photography', 'A full day of coverage with a same-week gallery of 300 edited images.'),
        ('Short reels for a salon', 'Eight vertical clips for Instagram and TikTok, with captions burned in.'),
    ],
    'tech': [
        ('Booking site for a guesthouse', 'A mobile-friendly site with room availability and M-Pesa payment links.'),
        ('Fee tracker for a primary school', 'Dashboard showing who has paid, who owes, and printable receipts.'),
        ('Online shop for a hardware store', 'Catalogue, cart and checkout, with stock numbers kept up to date.'),
        ('Inventory app for a pharmacy', 'A simple app for stock in, stock out and low-stock alerts.'),
        ('Landing page and contact forms', 'A fast one-page site with a quote form that emails the owner.'),
    ],
    'writing': [
        ('Website copy for a law firm', 'Home, About and Services pages rewritten in plain, confident English.'),
        ('Blog series on small business tax', 'Six short articles explaining KRA basics for shop owners.'),
        ('Brochure for a tour company', 'A tri-fold with itinerary text, in English and Kiswahili.'),
        ('Product descriptions for an online store', 'Eighty descriptions with the right keywords and a friendly tone.'),
        ('Newsletter for a school', 'Termly newsletter template and three issues written and edited.'),
    ],
    'business': [
        ('Inbox and calendar clean-up', 'A month of email sorting, replies drafted and meetings scheduled.'),
        ('Sales ledger in Excel', 'A tidy workbook with monthly totals, charts and a simple profit view.'),
        ('Data entry for a land survey', 'Two thousand plot records typed and checked against the scans.'),
        ('Event schedule for a church fundraiser', 'Run sheet, volunteer list and supplier contacts in one pack.'),
        ('Monthly books for a salon', 'Receipts sorted, mobile money statements matched and a summary sent.'),
    ],
    'trades': [
        ('Wardrobe and shelves in a two-bedroom flat', 'Built-in wardrobes and shelving, finished and fitted in four days.'),
        ('Kitchen plumbing replacement', 'New sink, taps and pipes for a house in Kilimani, no leaks since.'),
        ('Wiring for a small shop', 'New sockets, lighting and a distribution board that passed inspection.'),
        ('School uniforms in bulk', 'Sixty uniforms cut and sewn to measure over three weeks.'),
        ('Reception desk for a clinic', 'A solid wood reception desk built to size and varnished on site.'),
    ],
}
