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
the rank shown on each card. PhD and master’s students similarly appear under
Students while retaining their individual `role_label`. People are sorted by
`last_name`; use an unaccented spelling in that field when necessary, such as
`Alvares` for Álvares.

Profile links are optional. The supported fields are `email`, `website`,
`olemiss_profile`, `scholar`, `orcid`, `openalex_id`, `inspire`, and `cv`.

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
Give each scheduled meeting a `date_iso` value in `YYYY-MM-DD` format; the
website displays the newest meeting first automatically.
All invited talks—past and upcoming—belong in `_data/seminars.yml`. Add each
talk once using a `date_iso` value in `YYYY-MM-DD` format. The website sorts
the file automatically: the newest talks appear on the homepage, News &
Seminars page, and Meetings page, while `/seminars/` shows the complete list by
year. The newest seminar automatically receives the larger feature on the News
& Seminars page. Add an `abstract` to include one in that feature.

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
works from OpenAlex and INSPIRE, and writes the results to `_publications/`.
OpenAlex is the default source. Set `publication_source: inspire` on a profile
to use its `inspire` author link instead, or `publication_source: both` to use
both services. Records from both services are merged by DOI, arXiv ID, and
title.

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

The importer merges duplicate DOI, arXiv, and title records across sources. When both a
preprint and journal article exist, it keeps the journal metadata and retains
the arXiv link when possible. Files marked `generated: true` belong to the
importer; hand-written publication files are left alone.

OpenAlex occasionally combines people with similar names. For an affected
profile, `publication_filter: orcid` restricts the import to work curated on
that person's ORCID record. If the ORCID list is incomplete,
`publication_filter: physics` instead accepts only work that OpenAlex
classifies under Physics and Astronomy. Luca Bombelli uses the ORCID filter;
Anuradha Gupta and Nicholas MacDonald use the topic filter.

If INSPIRE has the more accurate author record, add the profile's `inspire`
link and set `publication_source: inspire`. Arindam Sharma uses this setting
because OpenAlex currently associates his author record with datasets but not
the corresponding papers.

If OpenAlex misclassifies a legitimate paper, add its `W...` identifier to the
profile's comma-separated `publication_include` field. This explicit exception
is applied before the profile filter.

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
