# GigConnect datasets

Everything the recommendation engine is trained on lives here, so it can be opened and checked. Only these README files are tracked in git. The data files themselves are gitignored.

| Folder | What goes in it | Who fills it |
|---|---|---|
| `raw/` | Kaggle downloads, unzipped and untouched, one folder per dataset | You, by hand |
| `processed/` | Cleaned job-posting corpus as CSV (`linkedin_corpus.csv`, `upwork_corpus.csv`, `freelancer_corpus.csv`, `combined_corpus.csv`) | `python manage.py import_job_corpus` |
| `platform/` | The GigConnect data a training run used: `gigs.csv`, `freelancers.csv`, `interactions.csv`, `applications.csv`. No names, emails, phone numbers or cover letters. | `train_recommender` / `export_training_data` |
| `samples/` | First 200 rows of every raw and processed file, for quick viewing | `import_job_corpus` |
| `reports/` | One Markdown report per import and per training run: row counts, rows dropped and why, top skills, synthetic share | The commands above |

## How the data is used

- Kaggle job postings (`raw/`, `processed/`) are used only to fit the TF-IDF vocabulary for the content-based model. They are never shown to users as gigs.
- The collaborative (SVD) model is trained only on GigConnect's own data (`platform/`), because no public dataset has freelancer-to-gig application history. Until the platform has real users, most of that data is synthetic seed data, flagged `is_synthetic`.

## Downloading

1. Sign in at kaggle.com and open each dataset link in the `raw/<dataset>/README.md` files.
2. Click Download, unzip, and put the files in that folder. Or, with your own Kaggle API token set up:
   `kaggle datasets download -d <ref> -p datasets/raw/<folder> --unzip`
3. Write the download date in that folder's README.

## Attribution

LinkedIn Job Postings (2023 to 2024) by Arsh Koneru, Kaggle, licensed CC BY-SA 4.0.
