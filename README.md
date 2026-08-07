# Gravity & Astrophysics at Ole Miss

A custom Jekyll site for the University of Mississippi Gravity and Astrophysics group. The design uses the university’s Pantone 186 C red (web equivalent `#C8102E`), a restrained scientific visual language, and content collections that researchers can maintain without editing templates.

## Run the site locally

Ruby 3.1 or newer is recommended.

```bash
bundle install
bundle exec jekyll serve
```

Open `http://localhost:4000`. GitHub Pages deployment is configured in `.github/workflows/pages.yml`; in the GitHub repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions**.

Before publishing, set `url` in `_config.yml` to the public domain. Set `baseurl` only if this is deployed beneath a path rather than at a domain root.

## Add a person

1. Copy `_people/_profile-template.md` to `_people/first-last.md`.
2. Remove the `published: false` line and replace the example fields.
3. Put a portrait in `assets/images/people/`, preferably a WebP or JPEG cropped close to a 4:5 ratio.
4. Set `photo` to the root-relative image path, such as `/assets/images/people/first-last.webp`.
5. Add the researcher’s ORCID if their papers should be imported automatically.

The `role` field controls where a member appears on the people page. Supported values are:

```text
full-professor
associate-professor
assistant-professor
postdoc
phd-student
masters-student
undergraduate
staff
affiliate
```

Use `role_label` for the exact text displayed on the card, and `order` to control ordering within a role. Lower numbers appear first. Set `alumni: true` to keep a profile available without showing it in the current directory.

If a member has no photo, the layout shows a quiet initial-based placeholder. Photos should have descriptive filenames; the template generates appropriate portrait alt text from the person’s name.

## Refresh publications

The importer reads ORCIDs from published member profiles, resolves each researcher through OpenAlex, fetches their works, de-duplicates group coauthored papers, and writes generated entries under `_publications/`.

```bash
python3 scripts/fetch_publications.py
```

Useful options:

```bash
# Preview file changes without writing
python3 scripts/fetch_publications.py --dry-run

# Change the earliest date considered
python3 scripts/fetch_publications.py --since 2020-01-01

# Also remove generated records no longer returned by OpenAlex
python3 scripts/fetch_publications.py --prune

# Include books, datasets, dissertations, and other non-paper work types
python3 scripts/fetch_publications.py --include-all-types
```

Set `OPENALEX_EMAIL` to a group contact email for [OpenAlex polite-pool API access](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication). The script uses the Python standard library and needs no package installation.

The scheduled workflow at `.github/workflows/publications.yml` runs every Monday, commits changed records, and triggers the site deployment. Optionally create a GitHub Actions repository variable named `OPENALEX_EMAIL`. The workflow can also be run manually from the Actions tab with a custom start date.

Generated files include `generated: true`; the importer updates only its own stable records and never overwrites hand-authored publication files. A publication may also be added manually using the same front matter fields shown in a generated entry.

### Important publication caveat

Automatic discovery is only as complete as each researcher’s ORCID/OpenAlex record. Encourage members to maintain their ORCIDs. Large-collaboration papers are included when a member is an indexed author, so LIGO or similar memberships can produce a substantial publication list. Review the first import before committing it, and use `--since` to set a sensible historical cutoff.

## Add research or news

- Research pages live in `_projects/`; their homepage summaries are in `_data/research_topics.yml`.
- News posts use the standard Jekyll filename `YYYY-MM-DD-short-title.md` under `_posts/`.
- Navigation is managed in `_data/navigation.yml`.
- Group-wide contact and affiliation text is in `_includes/footer.html` and `about.md`.

A minimal news post looks like:

```yaml
---
title: Our announcement
date: 2026-08-07
excerpt: A concise one-sentence summary.
---

Write the announcement in Markdown here.
```

## Brand and assets

The visual identity uses Ole Miss red but does not bundle a university trademark. Obtain approved logo artwork through University Marketing & Communications before adding a formal university mark. Depending on how the site represents the university, internal brand review may also be appropriate.

