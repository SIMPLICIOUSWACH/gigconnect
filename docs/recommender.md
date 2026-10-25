# The gig recommender

How gigs are recommended to freelancers, and how skill match scores are shown to clients. This is the
design as built in Sprint 5. What the API returns is in `api-endpoints.md`, and the tables are in
`erd.md`.

**Evaluation is Sprint 6.** Nothing here has been measured for accuracy: no split into training,
validation and test sets, no precision, recall or F1, no comparison with a random baseline. The settings
below are starting values. Do not quote an accuracy figure for this system from this document.

## What it does

- A freelancer sees **Recommended for You** on Browse Gigs and on their Dashboard: gigs they could apply to,
  best first, each with the skills it really shares with them.
- A client sees, for each applicant to their gig, a **skill match** in words (strong, good or some skill
  overlap) with the shared skills.
- Nothing is shown unless the trained model worked it out for that exact freelancer and gig. If the model is
  off, missing or cannot be read, the pages say so plainly. There is no guessing and no fallback number.

## The pipeline

```
Kaggle job postings --import_job_corpus--> datasets/processed/combined_corpus.csv --+
                                                                                     |
GigConnect gigs, freelancers, interactions, applications --------------------------> train_recommender
                                                                                     |
                  datasets/platform/ (snapshot)   datasets/reports/ (report)   backend/recommendations/artifacts/vNNNN/
                                                                                     +  RecommenderModelVersion row
                                                                                     |
                                         loaded once, cached --> /api/recommendations/ and the applicants list
```

Training is a manual command. There is no scheduled or automatic retraining.

## Features (`recommendations/features.py`)

Every piece of text is turned into a cleaned document in the same way, whether it comes from a GigConnect
gig, a freelancer or a Kaggle posting:

- Lowercased. HTML, web addresses and email addresses removed. English stop words removed. Numbers and
  single letters dropped.
- Each skill becomes one token, so "Machine Learning" stays together as `machine_learning`. Punctuation that
  carries meaning is kept apart: `C++` is `cplusplus`, `C#` is `csharp`, `.NET` is `dotnet`.
- **A gig's document** is its title, description, category name and skill tokens.
- **A freelancer's document** is their skill tokens, repeated three times so that skills outweigh a short
  free-text bio, followed by the words of the bio. Nothing else about a freelancer is used.
- Empty documents and duplicates are dropped before anything is learned.

**Not done: lemmatisation.** The proposal asks for it. It needs an extra language model download (WordNet or
spaCy) with install and CI cost, and it matters little for skill names, which come from a controlled list.
It is a known gap and could be added in `features.py`.

## The content model (`content.py`)

A `TfidfVectorizer` (sublinear term frequency, length-normalised, words kept if they appear in at least 3
documents and at most 80% of them) is fitted on the gig documents plus the external job-posting corpus. The
external postings let it know how skill and job words relate before GigConnect has many gigs of its own.

A freelancer becomes a vector in the same space, and the score for a gig is the **cosine similarity** of the
two, from 0 to 1. Because the vectors are length-normalised, a given freelancer and gig always get the same
score, whatever other gigs are scored with them.

**Platform weighting.** A few hundred Kenyan gigs would vanish among 30,000 foreign postings, so the platform's
gigs are repeated until they make up about 30% of the documents the vectoriser is fitted on
(`RECOMMENDER_PLATFORM_SHARE`). Without this, the skill words of the platform's own gigs fall below the
minimum document count and are lost (there is a test for this).

**Reasons.** `match_reasons` is the skills that appear on both the freelancer's profile and the gig, compared
after the cleaning above. It is worked out from the two skill lists and never from the score, so a reason is
never made up. A freelancer whose bio matches a gig but who shares no skill gets a score and no reasons.

**Candidates** (`candidates.py`). Only gigs the freelancer could apply to are scored: open, application
deadline not passed, not their own, and no application of theirs in any status (a withdrawn application means
they cannot apply again). The first two rules are the public feed's own, shared from `gigs/feed.py`, and a
test applies to every kind of gig through the real apply endpoint to check the two cannot drift apart.

## The collaborative model (`collaborative.py`)

A matrix with one row per freelancer and one column per gig holds **how strongly that freelancer showed
interest in that gig**. A `TruncatedSVD` finds hidden factors that explain the pattern, and multiplying them
back together gives a score for gigs a freelancer has not touched.

- **Weights** (`RECOMMENDER_INTERACTION_WEIGHTS`, `RECOMMENDER_APPLICATION_WEIGHTS`): view 1, search click 1,
  recommendation click 1, save 2, apply 3. An application counts as pending 3, under review 3, shortlisted 4,
  hired 5, and rejected or withdrawn 3 (the freelancer still applied). A freelancer and gig pair is worth the
  **strongest** signal, not the sum, so opening a gig fifty times counts once.
- **Absent, not zero.** A gig nobody has interacted with has no column, and a freelancer with no history has no
  row. Both get no collaborative score at all, which is different from a score of 0.
- **Minimums.** Below 10 freelancers, 20 gigs or 100 pairs the model is skipped and the reason is recorded.
  Whatever the settings say, fewer than 2 freelancers or 2 gigs is always refused.
- **Factors.** Up to `RECOMMENDER_SVD_COMPONENTS` (20), but **never more than half the smaller side of the
  matrix**. With almost as many factors as rows the model simply copies the data it was given, an unseen gig
  scores about zero, and the scores are noise. This was found in testing (see Limits).
- **Scale.** The raw scores are not on a 0 to 1 scale. At training the 95th percentile of the positive scores
  given to untouched gigs is stored on the model, and a raw score is divided by it and clipped. The scale is
  fixed, so a score does not depend on which other gigs are being scored.

## The hybrid score (`hybrid.py`)

```
hybrid = w * collaborative + (1 - w) * content        both on the 0 to 1 scale
```

**Cold start.** A freelancer who has interacted with fewer than 5 different gigs gets content scores only
(`w` is 0). From there `w` rises in equal steps over the next 20 gigs to a maximum of 0.5: 0.025 at 5 gigs,
0.25 at 14, 0.5 at 24 and beyond. All three numbers are settings. The scoring takes `w` as an argument, so
Sprint 6 can tune it without changing anything else.

A score has a `source`. It is `content` when there is no collaborative score (a gig posted after the last
training run, a freelancer who joined after it, no collaborative part, or cold start) and `hybrid` when it is
the blend. A gig posted after training is scored on its text with the saved vectoriser straight away.

## Client match score and bands (`matching.py`, `bands.py`)

For each applicant to a gig, the **content model's** score for that freelancer and that gig. It is shown in
words, not as a number, because a bare 0.18 looks more precise than a skill-overlap score is. The band is named
after what it measures:

| Band | Score | Shown only when |
|---|---|---|
| strong skill overlap | 0.30 or more | at least one skill is really shared |
| good skill overlap | 0.15 or more | at least one skill is really shared |
| some skill overlap | above 0 | at least one skill is really shared |

The cut-offs (`RECOMMENDER_BAND_STRONG`, `RECOMMENDER_BAND_GOOD`) come from scores measured on the development
data, where freelancers sharing a skill with a gig had a median score of 0.15 and a 90th percentile of 0.31.
That data is mostly synthetic, so they are **provisional**. All three bands look the same on screen, so no
colour suggests more certainty than the model has.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `RECOMMENDATIONS_ENABLED` | off | Switches recommendations and match scores on. Environment variable of the same name |
| `RECOMMENDER_DATA_DIR` | `<repo>/datasets` | Where the data, snapshots and reports live |
| `RECOMMENDER_ARTIFACT_DIR` | `backend/recommendations/artifacts` | Where trained models are saved |
| `RECOMMENDER_INCLUDE_SYNTHETIC` | on when `DEBUG` is on | Whether training uses the synthetic seed rows by default |
| `RECOMMENDER_CORPUS_MAX_ROWS` | 15000 / 15000 / 3000 | Most rows kept from Upwork / LinkedIn / Freelancer.com |
| `RECOMMENDER_PLATFORM_SHARE` | 0.3 | Share of fitted documents that are the platform's own |
| `RECOMMENDER_TFIDF_MIN_DF`, `_MAX_DF` | 3, 0.8 | Words in fewer than this many documents, or more than this share, are ignored |
| `RECOMMENDER_INTERACTION_WEIGHTS`, `RECOMMENDER_APPLICATION_WEIGHTS` | see above | Interest per interaction type and application status |
| `RECOMMENDER_SVD_COMPONENTS` | 20 | Most hidden factors (capped at half the smaller side) |
| `RECOMMENDER_SVD_MIN_FREELANCERS`, `_MIN_GIGS`, `_MIN_INTERACTIONS` | 10, 20, 100 | Below any of these the collaborative model is skipped |
| `RECOMMENDER_RANDOM_SEED` | 42 | Makes training repeatable |
| `RECOMMENDER_COLD_START_MIN_GIGS` | 5 | Fewer different gigs than this: content scores only |
| `RECOMMENDER_BLEND_RAMP_GIGS`, `_BLEND_MAX_WEIGHT` | 20, 0.5 | How fast and how far the collaborative weight rises |
| `RECOMMENDER_MODEL_CACHE_SECONDS` | 60 | How long a loaded model is trusted before asking whether a newer one exists |
| `RECOMMENDER_BAND_STRONG`, `_BAND_GOOD` | 0.30, 0.15 | The client's match band cut-offs |

## Training and retraining

```
python manage.py migrate
python manage.py import_job_corpus          # once, or when the Kaggle files change
python manage.py train_recommender          # each time you want a new model
```

Then set `RECOMMENDATIONS_ENABLED=True` for the server. Options: `--include-synthetic` or
`--no-include-synthetic` (default from the setting above), `--data-dir`, `--artifact-dir`.

- Each run makes a new model, numbered `v0001`, `v0002` and so on, and the newest is the one in use. The
  files are written to a temporary folder and renamed, and the database row is written last, so a run that
  fails part way changes nothing. Old versions are kept and can be deleted by hand.
- A running server picks up a new model within `RECOMMENDER_MODEL_CACHE_SECONDS`. A model is loaded the
  first time it is needed, never at startup, and then kept in memory. If its files are missing or cannot be
  read, the answer is "not available" (and the problem is logged), and if only the newest model cannot be
  read, the previous one keeps serving.
- A run writes a copy of the data it used to `datasets/platform/` and a report to
  `datasets/reports/training-YYYY-MM-DD.md`. Both are gitignored.
- **Retrain after deletions and after meaningful new data.** See Privacy.

## Synthetic data policy

Until the platform has real users, almost all of the data is synthetic seed data (`is_synthetic`). Training
can include it or leave it out (`--no-include-synthetic`), and **every trained model records how much of what
it learned from was synthetic**, separately for gigs and for interactions. As of the latest development run
that is 300 of 305 gigs (98%) and 890 of 893 pairs (100%). A model trained on that shows that the pipeline
works. It does not show that the recommendations are relevant to real freelancers.

The seeded interactions prefer gigs that share the freelancer's skills, which is why similar freelancers end
up with similar histories. That is made-up behaviour put there to give the model something to find.

## Privacy

- **A deleted freelancer drops out at the next training run.** Their account is deactivated, so they are
  excluded from the freelancer list, their interactions are deleted outright, and their applications are
  emptied of text and no longer count. They are in none of the matrix, the content documents or the snapshot.
  Tests train, delete an account, train again, and check that they appear nowhere.
- **Until that run, the old model still holds their row.** Deletion does not rewrite a model that has already
  been trained. What it holds for them is a row of factor values, not their interactions or profile. Retrain
  after deletions if that matters.
- **Deleting people can push the data below the minimum**, and then the next run has no collaborative part.
  The reason is recorded and the content model still works.
- A client is never shown a match score worked out from a deleted person's data. It is `null`.
- **The snapshot holds as little as it can**: ids, skills, interaction types, weights and times. No names,
  emails, phone numbers, bios or cover letters (tested).
- **The data export has nothing extra for the recommender.** No recommendations are stored per person, so
  there is nothing to export. The person's clicks on recommendations are interactions like any other, and are
  already in their export.

## Data sources

The external job postings are used **only to fit the content model's vocabulary and word weights**. They are
never shown to users as gigs and never go into the collaborative matrix, which is trained only on GigConnect's
own data, because no public dataset has freelancer-to-gig history.

| Dataset | Kaggle | Licence | Files used | Used for |
|---|---|---|---|---|
| LinkedIn Job Postings (2023 to 2024), by Arsh Koneru | https://www.kaggle.com/datasets/arshkon/linkedin-job-postings | CC BY-SA 4.0 | `postings.csv` | Title and description text |
| Upwork freelance jobs (+60k) | https://www.kaggle.com/datasets/ahmedmyalo/upwork-freelance-jobs-60k | Apache 2.0 | `Final_Upwork_Dataset.csv` | Title and description text, and the skill tags in `Category_1` to `Category_9` |
| Freelancer Data Analysis Jobs | https://www.kaggle.com/datasets/isaacoresanya/freelancer | MIT | `freelancer_job_postings.csv` | Not used by default (see below) |

**Attribution.** LinkedIn Job Postings (2023 to 2024) by Arsh Koneru, Kaggle, licensed CC BY-SA 4.0.

**Version and download date: to be filled in by the project owner.** Record the version shown on each Kaggle
page and the date downloaded in the README of each folder under `datasets/raw/`. The file dates on disk are
the dates Kaggle published them, not the download date.

**What is used from each, as measured on the first import** (the dated report is in `datasets/reports/`):

| Source | Rows read | Left out | Empty | Duplicate | Unique | Kept |
|---|---|---|---|---|---|---|
| Upwork | 63,950 | none | 4 | 3,550 | 60,396 | 15,000 |
| LinkedIn | 123,849 | 98,814 full-time | 1 | 3,673 | 21,361 | 15,000 |

- **LinkedIn full-time postings are left out**, as ordinary employment and not gig-style work. Contract,
  part-time, temporary, internship, volunteer and other postings are kept. LinkedIn has no clean skills
  column, so its documents have no skill tokens.
- **Rows kept are a seeded random sample** (`--seed`), capped per source, so no source drowns the others.
- LinkedIn is weaker for this purpose than Upwork. After removing full-time, its most common words are generic
  job-ad words (experience, team, benefits, health, care), and its 1,000 most common words overlap with
  Upwork's by only 0.38. It adds some noise, which the platform weighting and the word weights absorb.
- **Freelancer.com** is built in but off by default (`--sources freelancer`). It is data analysis only, and on
  its own it would skew the vocabulary.
- The Upwork download also contains four LinkedIn company tables (`companies.csv` and others). They hold no
  job text and are ignored.

The raw files, the processed corpus, the snapshots and the reports are all gitignored. Only the README files
under `datasets/` are tracked.

## Performance

Measured in Sprint 6 with `python manage.py time_recommendations --extra-open-gigs N --requests 3`, through the
full request stack, on the development database (production profile, content only), for the 33 verified
freelancers with skills: 99 requests each time. The extra open gigs are added inside a transaction and rolled
back, so nothing is left behind.

| Open gigs a freelancer could apply to | Before the gig cache (median / 95th / worst) | With the gig cache (median / 95th / worst) |
|---|---|---|
| 49 (the development data) | 49 / 66 / 143 ms | 36 / 42 / 92 ms |
| 2,049 | 673 / 804 / 892 ms | 104 / 174 / 211 ms |
| 2,999 | 1,019 / 1,155 / 1,237 ms | 136 / 209 / 244 ms |
| 5,049 | 1,755 / 1,875 / 2,029 ms | 219 / 301 / 401 ms |

Under the demo profile (which also blends the collaborative score) at 5,113 open gigs: median 211 ms, 95th
percentile 290 ms, worst 366 ms.

**Why it was slow.** A profile of one request showed the vectoriser was a small part of the time. Most of it went
on loading every candidate gig with its category and skills, cleaning its text and turning its skills into tokens,
on every request. Sprint 5's estimate of 0.1 to 0.15 ms per gig was too low: it was about 0.3 ms.

**The gig cache** (`recommendations/gig_cache.py`) keeps, per gig, its TF-IDF vector, its skills with their tokens
and when it was posted, keyed by the gig's id and `updated_at`. A request only reads the candidates' ids and
`updated_at`, builds the entries that are missing or out of date in one batch, and loads full gigs only for the page
it shows. The scores and reasons are exactly the ones the content model gave before (tested).

- Editing a gig saves it, which changes `updated_at`, so the next request rebuilds its entry. No signals. Gig edits
  set the skills before that save, in one transaction, so the new `updated_at` always comes with the new skills.
- The cache belongs to the loaded model: a new model version starts empty. Each server process has its own.
- If no model can be loaded, nothing is cached and the answer is "not available", as before.
- **The first request after a model loads builds the whole cache**: 0.3 s at 49 open gigs, 1.3 s at 3,000 and 2.1 s
  at 5,000 measured, once per process and model version. Every request after that is as in the table.
- Not noticed until the gig is next edited or a new model is loaded: renaming a category, or renaming or merging a
  skill, because neither changes a gig's `updated_at`.

The proposal asks for API responses under 500 ms. With the cache every request after the first meets it up to
5,000 open gigs.

## Limits found while building it

- **Too many factors memorise.** Allowed almost as many factors as rows, the model reproduced its input,
  scored unseen gigs at about zero, and normalised by noise. A matrix of 12 freelancers and 20 gigs failed a
  test for exactly this reason in CI. The cap at half the smaller side is the fix, and the right number of
  factors for real data is for Sprint 6 to tune.
- **Tied patterns can mix.** Two groups built identically give equal strongest patterns, and the SVD may
  return an arbitrary mix of them. Real data will not tie exactly, but tests have to avoid building it.
- **The scores have not been checked against anything**, and the bands come from synthetic data.
- **The collaborative part cannot show it is better than content.** That is what Sprint 6 measures.

## Where the build differs from the proposal

The written proposal was not available to compare against, so this lists what may differ:

- Lemmatisation is not done (above).
- LinkedIn full-time postings are excluded, and Freelancer.com is optional and off by default.
- Skill match is shown to clients as a band in words, not as a number or percentage.
- A `recommendation_click` interaction type was added, so clicks on the recommendations can be used later.
- Training is a manual command, not scheduled.
- The collaborative model learns from interactions and applications together, and the weights, cold-start
  numbers and minimums are starting values.

## What is left for Sprint 6

- The 70/15/15 split, precision, recall and F1 at K, the random baseline, and tuning `w`.
- Tuning the number of factors, the cold-start numbers and the band cut-offs on real data.
- User acceptance testing of whether the recommendations are relevant.
- Computing gig vectors once, if the number of open gigs grows.
