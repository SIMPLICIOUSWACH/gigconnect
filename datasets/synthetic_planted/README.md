# synthetic_planted

The ground truth of the planted seed world: synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy.

`python manage.py seed_planted` (run against its own database, see `docs/api-endpoints.md`) writes:

- `ground_truth.csv`: each planted freelancer's hidden taste group, home category, neighbouring category and favourite clients.
- `world.json`: the seed, the sizes and the counts of the world it made.

These files are the only place the groups are kept. They are never in the database, so no model can read them. They are read only after the models are fitted, to score how well the collaborative factors recover the groups. Like the rest of `datasets/`, only this README is tracked in git.
