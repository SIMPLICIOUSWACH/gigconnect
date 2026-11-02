# The gig recommender

How gigs are recommended to freelancers, and how skill match scores are shown to clients. This is the
design as built in Sprints 5 and 6. What the API returns is in `api-endpoints.md`, and the tables are in
`erd.md`.

**It was measured in Sprint 6 on synthetic data only** (see Evaluation). Any figure quoted from this document has to
say that: it shows the pipeline works and how its parts compare on seed data, not how relevant the recommendations
are to real freelancers.

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

**Cold start.** A freelancer who has interacted with fewer different gigs than the cold-start threshold gets content
scores only (`w` is 0). From there `w` rises in equal steps over the ramp to the largest weight. The three numbers come
from the recommender profile (`backend/config/recommender_profiles.json`, see the README):

- **production**: threshold 5, ramp 20, largest weight **0.5**, so `w` is 0.025 at 5 gigs and 0.5 from 24 gigs. The
  weight is the project owner's choice, not the tuning pick of 0 (see "Tuned values against Sprint 5").
- **demo** (the planted data): threshold 10, ramp 50, largest weight 0.5, so `w` is 0.01 at 10 gigs, 0.11 at 20 and
  0.31 at 40.

Rating a gig as relevant or not does not count as an interaction for this. The scoring takes `w` as an argument, which
is how the tuning tried other values without changing the code.

A score has a `source`. It is `content` when there is no collaborative score (a gig posted after the last
training run, a freelancer who joined after it, no collaborative part, cold start, or a weight of 0) and `hybrid` when
it is the blend. A gig posted after training is scored on its text with the saved vectoriser straight away.

## Client match score and bands (`matching.py`, `bands.py`)

For each applicant to a gig, the **content model's** score for that freelancer and that gig. It is shown in
words, not as a number, because a bare 0.18 looks more precise than a skill-overlap score is. The band is named
after what it measures:

| Band | Score (production) | Shown only when |
|---|---|---|
| strong skill overlap | 0.27 or more | at least one skill is really shared |
| good skill overlap | 0.13 or more | at least one skill is really shared |
| some skill overlap | above 0 | at least one skill is really shared |

The cut-offs (`RECOMMENDER_BAND_STRONG`, `RECOMMENDER_BAND_GOOD`) come from the profile. They were re-derived on the
validation split in Sprint 6 as the median and the 90th percentile of the content scores of freelancer and gig pairs
that share a skill (Sprint 5 had 0.15 and 0.30 from the same method on the whole development data). The demo profile
has 0.35 and 0.60 from the planted data. The data is synthetic, so they are **provisional**. All three bands look the same on screen, so no
colour suggests more certainty than the model has.

## Settings

Settings marked *profile* come from the recommender profile (`RECOMMENDER_PROFILE`, production by default), with the
production value shown.

| Setting | Default | What it does |
|---|---|---|
| `RECOMMENDER_PROFILE` | production | Which profile the app runs with: `production` or `demo`. Environment variable of the same name |
| `RECOMMENDATIONS_ENABLED` | off | Switches recommendations and match scores on. Environment variable of the same name; the demo profile switches it on |
| `RECOMMENDER_DATA_DIR` | `<repo>/datasets` | Where the data, snapshots and reports live |
| `RECOMMENDER_ARTIFACT_DIR` | `backend/recommendations/artifacts` (*profile*: `demo/` inside it for the demo) | Where trained models are saved |
| `RECOMMENDER_SNAPSHOT_FOLDER` | `platform` (*profile*: `platform/demo` for the demo) | Where in the data folder a training run writes its snapshot |
| `RECOMMENDER_INCLUDE_SYNTHETIC` | on when `DEBUG` is on | Whether training uses the synthetic seed rows by default |
| `RECOMMENDER_CORPUS_MAX_ROWS` | 15000 / 15000 / 3000 | Most rows kept from Upwork / LinkedIn / Freelancer.com |
| `RECOMMENDER_PLATFORM_SHARE` | 0.3 | Share of fitted documents that are the platform's own |
| `RECOMMENDER_TFIDF_MIN_DF`, `_MAX_DF` | 3, 0.8 | Words in fewer than this many documents, or more than this share, are ignored |
| `RECOMMENDER_INTERACTION_WEIGHTS`, `RECOMMENDER_APPLICATION_WEIGHTS` | see above | Interest per interaction type and application status |
| `RECOMMENDER_SVD_COMPONENTS` | 20 (*profile*) | Most hidden factors (capped at half the smaller side) |
| `RECOMMENDER_SVD_MIN_FREELANCERS`, `_MIN_GIGS`, `_MIN_INTERACTIONS` | 10, 20, 100 | Below any of these the collaborative model is skipped |
| `RECOMMENDER_RANDOM_SEED` | 42 | Makes training repeatable |
| `RECOMMENDER_COLD_START_MIN_GIGS` | 5 (*profile*) | Fewer different gigs than this: content scores only |
| `RECOMMENDER_BLEND_RAMP_GIGS`, `_BLEND_MAX_WEIGHT` | 20, 0.5 (*profile*) | How fast and how far the collaborative weight rises |
| `RECOMMENDER_MODEL_CACHE_SECONDS` | 60 | How long a loaded model is trusted before asking whether a newer one exists |
| `RECOMMENDER_BAND_STRONG`, `_BAND_GOOD` | 0.27, 0.13 (*profile*) | The client's match band cut-offs |

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
- A run writes a copy of the data it used to the profile's snapshot folder (`datasets/platform/`, or
  `datasets/platform/demo/` for the demo) and a report to `datasets/reports/training-YYYY-MM-DD.md`. Both are
  gitignored. The demo profile also keeps its models in a folder of its own, so it can never overwrite a production
  model.
- **Retrain after deletions and after meaningful new data.** See Privacy.

## Synthetic data policy

Until the platform has real users, almost all of the data is synthetic seed data (`is_synthetic`). Training
can include it or leave it out (`--no-include-synthetic`), and **every trained model records how much of what
it learned from was synthetic**, separately for gigs and for interactions. In the Sprint 5 development run
that was 300 of 305 gigs (98%) and 890 of 893 pairs (100%); every Sprint 6 evaluation was on 100% synthetic data. A model trained on that shows that the pipeline
works. It does not show that the recommendations are relevant to real freelancers.

The seeded interactions prefer gigs that share the freelancer's skills, which is why similar freelancers end
up with similar histories. That is made-up behaviour put there to give the model something to find.

A second seed, **synthetic_planted**, lives in a database of its own and is only used under the demo profile: hidden
taste groups that only a collaborative model could find (see the README and `docs/api-endpoints.md`). Its group labels
are kept in a file, never in the database, and are read only to score the models after they are fitted.

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
  there is nothing to export. The person's clicks on recommendations, and their answers to "Is this gig relevant to
  you?", are interactions like any other: they are in their export and deleted with their account.
- **Relevance answers never feed the recommender.** They are left out of training and do not count as history.

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

## Evaluation (Sprint 6)

**Every number here comes from a command that was run, on a named split, and the data is 100% synthetic.** It shows
that the pipeline works and how the parts compare on the seed data. It does not show how well the recommender serves
real freelancers. User acceptance testing (`docs/uat/`) is where real people judge relevance.

### Method

- **Relevant** means the freelancer applied to the gig, whatever became of the application. Views and clicks are not
  relevance. A stricter reading (shortlisted or hired only) is reported separately, with a warning when too few
  freelancers have one.
- **The split** (`build_evaluation_split`) is 70/15/15 per freelancer by time: each freelancer's applications in date
  order, the oldest 70% to train, the next 15% to validation and the newest 15% to test. At least 5 applications are
  needed (3, 1 and 1 at 5); freelancers with fewer stay in train only. The split is saved with a fingerprint and
  reused, so results stay comparable.
- **Nothing held out reaches training.** The vectoriser is fitted only on gigs posted before the earliest cut-off, and
  the collaborative models only on interactions before each freelancer's own cut-off and never on a gig held out for
  them. Application statuses are taken as they were at the cut-off. Tests fail if a held-out interaction gets in.
- **Candidates are the gigs open at the time**: posted by the end of the part and still taking applications at some
  point in it, not the freelancer's own and not already applied to. The live feed's rules are not used, because most
  held-out gigs have since closed.
- **Metrics**: precision, recall and F1 at K = 5 and 10 (the headline, as in the proposal), with K = 20 and hit rate as
  supplementary columns. Each is averaged over freelancers with a 95% bootstrap interval.
- **Compared**: a random baseline (20 seeds, with the spread), popularity, content only, collaborative on applications
  and hiring only (the proposal's reading), collaborative on all interactions (as built), and the hybrid.
- **Tuning** (`tune_recommender`) used the validation part only: 240 combinations of the largest collaborative weight,
  the ramp, the number of factors and the cold-start threshold. The rule, fixed in advance: pick by the mean of F1@5
  and F1@10, and change a default only if the gain beats the random spread and its paired 95% interval is above zero.
- **The test part was scored once** per data set (`evaluate_recommender --split test --final`), after tuning, and the
  run is logged.

### Two data sets

| | Skill-overlap seed (production profile) | Planted seed (demo profile) |
|---|---|---|
| What it is | The ordinary development seed. Freelancers favour gigs that share their skills, about 5 to 1 | A separate world with hidden taste groups (budget, urgency, client, location) behind about 40% of applications |
| Freelancers evaluated | 30 (1 more with too few applications) | 250 |
| Applications: train / validation / test | 421 / 92 / 92 | 3,500 / 744 / 744 |
| Synthetic | 100% | 100% |
| Candidate gigs per freelancer (test, median) | 102 | 127 |

The skill-overlap seed favours the content model by construction. The planted seed was built to check that the
collaborative part can find a pattern when one exists; it is labelled **synthetic_planted - demonstrates pipeline
mechanics, not real-world accuracy** everywhere, and it never sets the live defaults.

### Final test results

Mean over freelancers, 95% bootstrap interval in brackets.

**Skill-overlap seed, production profile** (split `ea6b321679335efd`, 30 freelancers, 92 right answers):

| Method | Precision@5 | Precision@10 | Recall@5 | Recall@10 | F1@5 | F1@10 |
|---|---|---|---|---|---|---|
| Random (20 seeds) | 0.030 (0.023 to 0.038) | 0.029 (0.024 to 0.033) | 0.049 (0.037 to 0.062) | 0.092 (0.078 to 0.107) | 0.037 (0.029 to 0.047) | 0.043 (0.037 to 0.050) |
| Popularity | 0.020 (0.000 to 0.047) | 0.023 (0.010 to 0.040) | 0.031 (0.000 to 0.067) | 0.075 (0.033 to 0.128) | 0.024 (0.000 to 0.055) | 0.036 (0.015 to 0.061) |
| Content only | 0.107 (0.073 to 0.140) | 0.120 (0.090 to 0.153) | 0.172 (0.117 to 0.231) | 0.389 (0.294 to 0.489) | 0.131 (0.090 to 0.174) | 0.183 (0.138 to 0.233) |
| Collaborative only (all interactions) | 0.020 (0.000 to 0.047) | 0.027 (0.010 to 0.047) | 0.033 (0.000 to 0.078) | 0.086 (0.031 to 0.153) | 0.025 (0.000 to 0.058) | 0.041 (0.015 to 0.071) |
| Chosen setting (weight 0, so content only) | 0.107 (0.073 to 0.140) | 0.120 (0.090 to 0.153) | 0.172 (0.117 to 0.231) | 0.389 (0.294 to 0.489) | 0.131 (0.090 to 0.174) | 0.183 (0.138 to 0.233) |

**Planted seed, demo profile, synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy** (split
`7f920483a6bc6c71`, 250 freelancers, 744 right answers):

| Method | Precision@5 | Precision@10 | Recall@5 | Recall@10 | F1@5 | F1@10 |
|---|---|---|---|---|---|---|
| Random (20 seeds) | 0.024 (0.021 to 0.026) | 0.024 (0.022 to 0.025) | 0.040 (0.036 to 0.043) | 0.080 (0.075 to 0.084) | 0.029 (0.027 to 0.032) | 0.036 (0.034 to 0.039) |
| Popularity | 0.033 (0.023 to 0.042) | 0.026 (0.020 to 0.032) | 0.056 (0.040 to 0.073) | 0.087 (0.067 to 0.108) | 0.041 (0.029 to 0.053) | 0.039 (0.030 to 0.049) |
| Content only | 0.127 (0.108 to 0.147) | 0.098 (0.088 to 0.109) | 0.208 (0.178 to 0.239) | 0.331 (0.295 to 0.368) | 0.156 (0.133 to 0.181) | 0.151 (0.134 to 0.167) |
| Collaborative only (2 factors) | 0.039 (0.029 to 0.050) | 0.027 (0.021 to 0.033) | 0.066 (0.048 to 0.083) | 0.091 (0.072 to 0.112) | 0.048 (0.036 to 0.062) | 0.042 (0.032 to 0.051) |
| Chosen hybrid (weight 0.5, ramp 50, 2 factors, cold start below 10) | 0.130 (0.110 to 0.150) | 0.106 (0.095 to 0.117) | 0.213 (0.182 to 0.245) | 0.354 (0.319 to 0.391) | 0.160 (0.137 to 0.184) | 0.161 (0.145 to 0.178) |

Hit rate@10 (supplementary): skill-overlap, random 0.267 and content 0.800; planted, random 0.217, content 0.656 and the
hybrid 0.700. Every other number, including K = 20, is in the reports in `datasets/reports/`.

### Tuned values against Sprint 5

| Setting | Sprint 5 | Production (skill-overlap pick) | Demo (planted pick) |
|---|---|---|---|
| Largest collaborative weight | 0.5 | **0** (content only) | 0.5 |
| Ramp (gigs) | 20 | 20 (no effect at weight 0) | 50 |
| Hidden factors | 20 | 20 (no effect at weight 0) | 2 |
| Cold-start threshold (gigs) | 5 | 5 (no effect at weight 0) | 10 |
| Match bands, good and strong | 0.15, 0.30 | 0.13, 0.27 | 0.35, 0.60 |

- **Production now runs at weight 0.5, not the tuning pick.** The project owner set it on 30 October 2026 so the
  hybrid runs on the main database. These are the same weight, ramp and factors as the Sprint 5 hybrid, which scored
  lower than content only below, so the evaluation does not support this setting and the scores in this document
  describe weight 0. They have not been re-measured, and the test part must not be scored again.
- **Production, weight 0 (the tuning pick).** On validation, content only scored 0.089 (mean of F1@5 and F1@10) against 0.030 for the
  Sprint 5 hybrid: a gain of 0.058, larger than the random spread (0.012), with a paired interval of 0.013 to 0.110.
  The rule therefore changed the default. The best hybrid with any collaborative weight scored 0.083.
- **Why the collaborative part adds nothing here.** On the skill-overlap seed the collaborative matrix (31 freelancers
  by 242 gigs, 7% filled) explains no more than a random matrix of the same shape (`check_collaborative_readiness`),
  its scores rank the right answers at chance, and it cannot even tell which gigs share a freelancer's skills (an AUC
  of 0.51). The only pattern the seed has is skill overlap, which the content model already sees, and half the
  right answers are gigs nobody else applied to in train.
- **Demo, a hybrid.** On the planted seed the collaborative matrix has clear structure above random (26.4% explained
  at 10 factors against 13.2% and 19.6% for the two random matrices), its factors recover the hidden groups (a pair
  AUC of 0.709 against 0.500 by chance and 0.502 for the content profiles), and the chosen hybrid beat content only
  on validation by 0.012 (paired interval 0.005 to 0.019, random spread 0.005).
- **Bands** were re-derived on validation as the median and the 90th percentile of the content scores of pairs that
  share a skill (781 pairs on the skill-overlap seed: 0.129 and 0.271). Still provisional.

### What the numbers show and do not show

- **They show** that the evaluation is sound (no leakage, a random baseline at the level chance predicts, a pipeline
  that finds a planted collaborative pattern and misses none that is absent), that the content model ranks the right
  answers well above random on both data sets, and that the collaborative part helps only when the data has a
  collaborative pattern.
- **They do not show** how relevant the recommendations are to real freelancers. All the data is synthetic, the
  skill-overlap seed favours the content model by construction, and the planted seed was built to have the pattern
  that was then found.
- On the planted test set the hybrid is ahead of content only (F1@10 0.161 against 0.151), but the intervals overlap,
  so the test set alone does not confirm the gain that validation showed.
- 30 freelancers is a small sample: the intervals on the skill-overlap seed are wide.
- **When there are real users**, run `check_collaborative_readiness` and `tune_recommender` again. If the readiness
  check finds structure, the evidence may support the collaborative weight production now runs with.

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
  test for exactly this reason in CI. The cap at half the smaller side is the fix. Sprint 6 tuning found fewer factors
  (2 to 10) did better than the cap on both seeds.
- **Tied patterns can mix.** Two groups built identically give equal strongest patterns, and the SVD may
  return an arbitrary mix of them. Real data will not tie exactly, but tests have to avoid building it.
- **The blend mixes two scales.** The collaborative score is divided by a fixed scale and clipped to 0 to 1, and
  within one freelancer's candidates it spreads about 4.6 times as widely as the content score. With a weight above 0
  it can swamp the content score; a z-scored blend did better in a diagnostic run. Production uses a weight of 0, so
  this does not affect it today.
- **The collaborative part needs data with a collaborative pattern.** On the skill-overlap seed it was at chance; on
  the planted seed it found the hidden groups. Check with `check_collaborative_readiness` before relying on it.

## Where the build differs from the proposal

Compared with the written proposal (shared in Sprint 6):

- **No lemmatisation.** The proposal asks for it. It needs an extra language model download, and it matters little for
  skill names, which come from a controlled list.
- **Category is part of the TF-IDF text**, not a one-hot feature. The category name is cleaned and added to the gig's
  document like the title and skills.
- **The collaborative model learns from more than applications and hiring.** The proposal describes application and
  hiring data; the build also uses views, search clicks, recommendation clicks and saves. Both were measured on the
  same split in Sprint 6 ("applications and hiring only" against "all interactions"); neither beat content only on
  the skill-overlap seed.
- **Production runs the hybrid at a weight tuning did not pick.** Tuning on the validation split chose a weight of 0,
  because the seed data has no collaborative pattern. The project owner set 0.5 so the hybrid the proposal describes
  is live. The reported production scores are for weight 0.
- **No stored recommendations table and no notifications table.** Recommendations are worked out on each request.
  Notifications (real-time and email) are not built yet; they are planned first in Sprint 7.
- **The model is loaded the first time it is needed, not at startup**, so a missing or broken model can never stop the
  app from starting.
- **Text choices instead of database ENUMs.** Statuses and types are Django text choices, checked by the app, not
  PostgreSQL ENUM types. This is kept on purpose: it avoids schema churn when a value is added.
- **Dataset choices.** The external postings (Upwork and LinkedIn) only fit the content model's vocabulary. LinkedIn
  full-time postings are left out as ordinary employment, and Freelancer.com is optional and off by default. The
  collaborative model uses GigConnect's own data only.
- **Skill match is shown to clients as a band in words**, not a number or percentage.
- **Added beyond the proposal:** the `recommendation_click`, `recommendation_relevant` and
  `recommendation_not_relevant` interaction types; a popularity baseline, K = 20, hit rate and bootstrap intervals in
  the evaluation; tuning of the ramp, factors and cold-start threshold as well as the weight; the planted seed and the
  demo profile; and, in the UAT kit, the System Usability Scale as a labelled optional extra.
- **Training is a manual command**, not scheduled.

## What is left

- **User acceptance testing**: the kit is ready in `docs/uat/` and the result sheets are empty.
- **Re-checking on real data**: once there are real users, run `check_collaborative_readiness` and
  `tune_recommender` again, and re-derive the band cut-offs.
- **The cold-start note** on the Recommended for You section, which does not fit a weight of 0.
- **Notifications** (Sprint 7).
- The first request after a model loads builds the gig cache (about 2 seconds at 5,000 open gigs); it could be warmed
  in advance if that matters.
