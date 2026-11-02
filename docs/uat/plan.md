# UAT plan

## Why

The proposal's fourth objective is to test and validate the system for functionality, usability and accuracy of the
matching model. The offline evaluation (`docs/recommender.md`) measures the model on held-out applications, mostly
synthetic. UAT adds what that cannot: whether real people can do the main tasks, where the interface gets in their
way, and whether they find their recommendations relevant.

## Who

- **Strathmore University students, in both roles**, as the proposal says: some act as freelancers, some as clients.
- **Suggested numbers: 5 to 8 freelancers and 3 to 5 clients.** The proposal does not give a number. Five users per
  role is a common rule of thumb for finding most usability problems; more freelancers are suggested because they also
  rate recommendations, and each one adds ten ratings.
- Participants should have skills a gig on the platform could ask for (design, writing, web development, data entry,
  and so on), so their recommendations can be judged.
- The proposal names the limit: a small group from one university does not represent the wider Kenyan freelance
  population. The results are read with that in mind.

## Consent and privacy

- Participation is voluntary. Before starting, each participant reads a short consent note (what the session is, that
  it is recorded only as notes, that they can stop at any time) and agrees.
- Participants create their own accounts. Only what sign-up asks for is collected. Names do not go into the results
  sheets: participants are numbered (F1, F2, ... and C1, C2, ...).
- When the results are recorded, participant accounts are deleted from Settings (which also deletes their relevance
  answers and other activity).

## Setting up before the sessions

- Run the app under the **production profile** (the default), which is what real users get: content-based
  recommendations, with the settings chosen by tuning. The demo profile is planted data and is not for UAT.
- `RECOMMENDATIONS_ENABLED=True`, and a model trained on the current data (`python manage.py train_recommender`).
- The seeded gigs give freelancers something to be recommended and to apply to. They are synthetic, which is a limit
  on what the relevance ratings mean (see relevance-rating.md).
- For the client tasks, have one prepared freelancer account apply to the participant's gig during task C2 so that
  there is an applicant to review in C3 (see client-tasks.md).
- Check that email verification works on the machine used, or verify participant accounts by hand in the admin.
- Clear the relevance answers of any earlier trial run (or start from a fresh database), so only participants' answers
  are counted.

## How a session runs (about 45 minutes)

| Part | Time | What happens |
|---|---|---|
| Welcome and consent | 5 min | Explain the session. The participant agrees. |
| Tasks | 20 to 25 min | The participant works through the task script for their role, thinking aloud. The observer does not help unless the participant is stuck for more than two minutes, and notes it if they do. |
| Relevance rating (freelancers) | 5 to 10 min | The participant rates their first ten recommendations (relevance-rating.md). |
| SUS (optional) | 3 min | Only if the optional System Usability Scale is used (sus.md). |
| Debrief | 5 min | What was easy, what was hard, anything missing. |

## What is measured

| Measure | How | Where it is recorded |
|---|---|---|
| Task success | Completed alone, completed with help, or not completed | results.md, task tables |
| Time on task | From reading the task to finishing it | results.md, task tables |
| Errors and confusion | What the participant tried that did not work, and what they said | results.md, notes |
| Perceived relevance | Rated relevant out of rated, within the top 5 and the top 10 | `python manage.py summarise_relevance`, copied into results.md |
| Usability problems | Nielsen's heuristics, screen by screen, with a severity | heuristic-checklist.md, summarised in results.md |
| SUS score (optional) | The standard ten statements and scoring | sus.md, summarised in results.md |

## The heuristic evaluation

Separate from the participant sessions. Three to five evaluators (for example the developer and two classmates) each
go through every screen in heuristic-checklist.md on their own, then the findings are merged and each problem gets
one agreed severity.

## After the sessions

1. Run `python manage.py summarise_relevance` and copy the counts into results.md.
2. Fill in the task tables and the summary of problems.
3. Delete the participant accounts.
4. Write up the findings next to the offline evaluation: where they agree, where they do not, and what the limits are.
