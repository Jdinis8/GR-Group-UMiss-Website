# Ole Miss Gravity and Astrophysics group website

This repository contains the Jekyll site for the University of Mississippi
Gravity and Astrophysics group. Most routine updates only require editing a
Markdown or YAML file.

## Preview the site locally

Install Ruby 3.1 or newer, then run:

```bash
bundle install
bundle exec jekyll serve
```

The site will be available at
<http://localhost:4000/GR-Group-UMiss-Website/>. Stop the server with `Ctrl+C`.

## Add a current member

1. Copy `_people/_profile-template.md` to a file named after the person, for
   example `_people/jane-doe.md`.
2. Remove `published: false` and fill in the profile fields.
3. If a portrait is available, place it in `assets/images/people/` and set the
   `photo` field. A 4:5 WebP or JPEG works well. Profiles without a photo use an
   initial placeholder.
4. Add an ORCID or OpenAlex ID if the publication importer should follow this
   person.

The available roles are:

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

All professor ranks appear together under Faculty, but `role_label` preserves
the rank shown on each card. People are sorted by `last_name`; use an
unaccented spelling in that field when necessary, such as `Alvares` for
Álvares.

Profile links are optional. The supported fields are `email`, `website`,
`scholar`, `orcid`, `openalex_id`, `inspire`, and `cv`.

## Add a former member

Former members are listed in `_data/former_members.yml`. Add the name under the
appropriate group, with a website or obfuscated contact address if available:

```yaml
- name: Jane Doe
  website: https://example.edu/jane
  contact: jane at example.edu
```

These entries appear only in the Past members section. They are not included
in publication imports.

## Add news

Create a Markdown file under `_posts/` using the date in its filename:

```text
_posts/2026-08-07-short-title.md
```

A post needs only a title, a short summary, and its text:

```yaml
---
title: A short, descriptive title
excerpt: One sentence for the homepage and News page.
---

Write the announcement here.
```

Items from 2015 onward belong in regular Group news. For an item from before
2015, add `archive: true` so it appears under “From the archive” and stays off
the homepage.

## Update group meetings

The weekly schedule and meeting contacts are stored in `_data/meetings.yml`.
All invited talks—past and upcoming—belong in `_data/seminars.yml`. Add each
talk once using a `date_iso` value in `YYYY-MM-DD` format. The website sorts
the file automatically: the newest talks appear on the homepage, News &
Seminars page, and Meetings page, while `/seminars/` shows the complete list by
year. Add `featured: true` and an `abstract` when a talk should receive the
larger feature on the Meetings page.

```yaml
- date_iso: '2026-09-10'
  speaker: Jane Doe
  affiliation: Example University
  title: A seminar title
```

## Edit the research pages

The six detailed research pages live in `_projects/`. Their shorter homepage
and Research-page descriptions are in `_data/research_topics.yml`. Update both
places when adding or renaming an area.

## Update publications

The importer reads the identifiers in current member profiles, downloads their
works from OpenAlex, and writes the results to `_publications/`.

Preview an update first:

```bash
python3 scripts/fetch_publications.py --dry-run --prune
```

If the preview looks right, apply it:

```bash
python3 scripts/fetch_publications.py --prune
```

Other useful options are:

```bash
# Only consider papers from this date onward
python3 scripts/fetch_publications.py --since 2020-01-01

# Include datasets, dissertations, and other non-paper records
python3 scripts/fetch_publications.py --include-all-types
```

The default start date is 1980. Be careful when combining a later `--since`
date with `--prune`: older generated files will be removed.

The importer merges duplicate DOI, arXiv, and title records. When both a
preprint and journal article exist, it keeps the journal metadata and retains
the arXiv link when possible. Files marked `generated: true` belong to the
importer; hand-written publication files are left alone.

OpenAlex occasionally combines two people with similar names. For an affected
profile, `publication_filter: orcid` restricts the import to work listed on
that person's ORCID record. Luca Bombelli's profile uses this setting because
his OpenAlex record also contains work by another L. Bombelli.

The workflow in `.github/workflows/publications.yml` runs every Monday. It can
also be started manually from the repository's Actions tab. The optional
repository variable `OPENALEX_EMAIL` supplies a contact address to the OpenAlex
API.

## Publish with GitHub Pages

Deployment is handled by `.github/workflows/pages.yml`. In the repository
settings, choose **Pages → Build and deployment → GitHub Actions**.

The current GitHub Pages address is `https://jdinis8.github.io/GR-Group-UMiss-Website/`,
so `_config.yml` uses `https://jdinis8.github.io` as `url` and
`/GR-Group-UMiss-Website` as `baseurl`. If the site later moves to a custom
domain, update `url` and set `baseurl` back to an empty string.

## Other useful files

- `_data/navigation.yml`: main navigation
- `_data/meetings.yml`: weekly meeting schedule and contacts
- `_data/seminars.yml`: all invited seminars
- `_data/roles.yml`: People-page sections
- `_includes/footer.html`: footer and group contact details
- `about.md`: About page and collaborations
- `brand.md`: future logo and branding downloads
- `assets/css/main.css`: site styling

The site uses Ole Miss red (`#C8102E`) but does not include an official
university logo. Use approved artwork if a formal university mark is added.
