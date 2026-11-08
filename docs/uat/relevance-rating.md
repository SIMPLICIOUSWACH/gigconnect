# Rating the recommendations

The proposal asks participants to rate the perceived relevance of their top-K recommendations, as a subjective check
next to the offline precision and recall at K = 5 and 10.

## What the participant does

On the Browse Gigs page, the "Recommended for You" section shows up to ten gigs, best first. Under each one is the
question **"Is this gig relevant to you?"** with two answers, **Relevant** and **Not relevant**. After answering, the
page says "Thanks, noted". An answer can be changed by choosing the other one.

Read this to the participant:

"Please answer the question under each of the recommended gigs, from the first to the tenth. Relevant means you would
seriously consider applying for it, given your skills and what you are looking for. Go with your first impression.
You can change an answer if you change your mind."

If fewer than ten gigs are recommended (a participant with unusual skills may get fewer), they rate all that are shown,
and the observer notes how many there were.

## How the answers are stored

Each answer is saved with the gig's place in the list at the time, as a `recommendation_relevant` or
`recommendation_not_relevant` interaction. Only the latest answer per participant and gig is kept. These answers never
feed the recommender: they are not used in training and do not change how a participant's recommendations are blended.
They are part of the participant's data export and are deleted with their account.

## How they are counted

```
python manage.py summarise_relevance
```

prints, for real accounts only (synthetic seed accounts are left out):

- the number of answers and of participants, and how many were rated relevant;
- **within the top 5**: rated relevant out of rated, for gigs that were in places 1 to 5;
- **within the top 10**: the same for places 1 to 10;
- the counts per gig.

"Rated relevant out of rated within the top 5" is the participants' own precision at 5. Copy the counts into
results.md. The command shows counts only, and nothing about these answers is shown to participants.

## Limits

- The gigs that can be recommended are mostly seeded, synthetic gigs. A participant rates whether such a gig would
  suit them, which is a fair question, but they are not real postings.
- A small group, rating ten gigs each, gives a rough figure. Report the counts, not a percentage alone.
