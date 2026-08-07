#!/usr/bin/env python3
"""Build Jekyll publication files from ORCIDs in _people/*.md.

The script uses only Python's standard library. It resolves each ORCID to an
OpenAlex author, fetches that author's works, de-duplicates them, and writes
machine-managed Markdown files to _publications/. Hand-authored files are never
overwritten.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

API_ROOT = "https://api.openalex.org"
ALLOWED_TYPES = {"article", "preprint", "book-chapter", "review"}
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


@dataclass(frozen=True)
class Member:
    name: str
    orcid: str
    source: Path


class OpenAlexClient:
    def __init__(self, email: str = "", pause: float = 0.1) -> None:
        self.email = email
        self.pause = pause

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        if self.email:
            query["mailto"] = self.email
        url = f"{API_ROOT}/{path.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "um-gravity-publications/1.0"},
        )
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    result = json.load(response)
                time.sleep(self.pause)
                return result
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < 3:
                    time.sleep(2**attempt)
        raise RuntimeError(f"OpenAlex request failed for {url}: {last_error}")

    def resolve_author(self, orcid: str) -> dict[str, Any]:
        return self.get(f"authors/https://orcid.org/{orcid}")

    def works(self, author_id: str, since: str) -> Iterable[dict[str, Any]]:
        cursor = "*"
        while cursor:
            payload = self.get(
                "works",
                {
                    "filter": f"authorships.author.id:{author_id},from_publication_date:{since}",
                    "per-page": "200",
                    "cursor": cursor,
                    "select": (
                        "id,doi,title,display_name,publication_year,publication_date,type,"
                        "authorships,primary_location,best_oa_location,locations,ids,biblio,"
                        "open_access"
                    ),
                },
            )
            yield from payload.get("results", [])
            cursor = payload.get("meta", {}).get("next_cursor")


def front_matter(path: Path) -> dict[str, Any]:
    """Read the small scalar subset needed from a Jekyll profile."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    try:
        raw = text.split("---", 2)[1]
    except IndexError:
        return {}
    values: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def find_members(directory: Path) -> list[Member]:
    members: list[Member] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        data = front_matter(path)
        if str(data.get("published", "true")).lower() == "false":
            continue
        orcid = str(data.get("orcid", "")).removeprefix("https://orcid.org/").strip()
        if not orcid:
            continue
        if not ORCID_PATTERN.fullmatch(orcid):
            print(f"warning: invalid ORCID {orcid!r} in {path}", file=sys.stderr)
            continue
        members.append(Member(str(data.get("name", path.stem)), orcid, path))
    return members


def clean_doi(value: str | None) -> str:
    return (value or "").removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def arxiv_id(work: dict[str, Any]) -> str:
    arxiv = str(work.get("ids", {}).get("arxiv", ""))
    if arxiv:
        return arxiv.removeprefix("https://arxiv.org/abs/")
    for location in work.get("locations") or []:
        landing = str(location.get("landing_page_url") or "")
        if "arxiv.org/abs/" in landing:
            return landing.split("arxiv.org/abs/", 1)[1]
    return ""


def venue_name(work: dict[str, Any]) -> str:
    for key in ("primary_location", "best_oa_location"):
        source = (work.get(key) or {}).get("source") or {}
        if source.get("display_name"):
            return str(source["display_name"])
    return ""


def author_names(work: dict[str, Any]) -> list[str]:
    names = []
    for authorship in work.get("authorships") or []:
        name = (authorship.get("author") or {}).get("display_name")
        if name:
            names.append(str(name))
    return names


def author_summary(names: list[str]) -> str:
    if len(names) <= 12:
        return ", ".join(names)
    return f"{', '.join(names[:8])}, and {len(names) - 8} collaborators"


def group_authors(work: dict[str, Any], openalex_members: dict[str, str]) -> list[str]:
    matches = []
    for authorship in work.get("authorships") or []:
        author_id = str((authorship.get("author") or {}).get("id", "")).rsplit("/", 1)[-1]
        if author_id in openalex_members:
            matches.append(openalex_members[author_id])
    return sorted(set(matches))


def work_key(work: dict[str, Any]) -> str:
    doi = clean_doi(work.get("doi"))
    if doi:
        return f"doi:{doi.lower()}"
    title = str(work.get("display_name") or work.get("title") or "")
    year = str(work.get("publication_year") or "")
    if title:
        return f"title:{year}:{slugify(title, 120)}"
    return str(work.get("id", "")).lower()


def slugify(value: str, limit: int = 58) -> str:
    value = value.encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:limit].rstrip("-") or "publication"


def yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render(work: dict[str, Any], matched_members: list[str]) -> str:
    names = author_names(work)
    openalex = str(work.get("id", ""))
    year = work.get("publication_year") or str(work.get("publication_date", ""))[:4]
    date = work.get("publication_date") or f"{year}-01-01"
    biblio = work.get("biblio") or {}
    best_oa = work.get("best_oa_location") or {}
    pdf = best_oa.get("pdf_url") or ""
    lines = [
        "---",
        "generated: true",
        f"title: {yaml_string(work.get('display_name') or work.get('title') or 'Untitled')}",
        f"date: {yaml_string(date)}",
        f"year: {year}",
        f"authors_display: {yaml_string(author_summary(names))}",
        f"authors: {json.dumps(names, ensure_ascii=False)}",
        f"group_authors: {json.dumps(matched_members, ensure_ascii=False)}",
        f"venue: {yaml_string(venue_name(work))}",
        f"volume: {yaml_string(biblio.get('volume') or '')}",
        f"issue: {yaml_string(biblio.get('issue') or '')}",
        f"pages: {yaml_string(biblio.get('first_page') or '')}",
        f"doi: {yaml_string(clean_doi(work.get('doi')))}",
        f"arxiv: {yaml_string(arxiv_id(work))}",
        f"openalex: {yaml_string(openalex)}",
        f"pdf: {yaml_string(pdf or '')}",
        f"work_type: {yaml_string(work.get('type') or '')}",
        "---",
        "",
        "<!-- This file is maintained by scripts/fetch_publications.py. -->",
        "",
    ]
    return "\n".join(lines)


def output_path(directory: Path, work: dict[str, Any]) -> Path:
    year = work.get("publication_year") or "undated"
    title = str(work.get("display_name") or work.get("title") or "publication")
    work_id = str(work.get("id", "")).rsplit("/", 1)[-1]
    suffix = work_id.lower() or hashlib.sha1(work_key(work).encode()).hexdigest()[:10]
    existing = sorted(directory.glob(f"*-{suffix}.md"))
    if existing:
        return existing[0]
    return directory / f"{year}-{slugify(title)}-{suffix}.md"


def is_generated(path: Path) -> bool:
    try:
        return "\ngenerated: true\n" in path.read_text(encoding="utf-8")[:500]
    except OSError:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--people", type=Path, default=Path("_people"), help="profile directory")
    parser.add_argument("--output", type=Path, default=Path("_publications"), help="publication directory")
    parser.add_argument("--since", default="2010-01-01", help="earliest publication date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing files")
    parser.add_argument("--prune", action="store_true", help="remove generated files no longer returned by OpenAlex")
    parser.add_argument("--include-all-types", action="store_true", help="include books, datasets, and other non-paper works")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dt.date.fromisoformat(args.since)
    except ValueError:
        print("error: --since must be YYYY-MM-DD", file=sys.stderr)
        return 2

    members = find_members(args.people)
    if not members:
        print(f"No published profiles with valid ORCIDs found in {args.people}.")
        print("Add an ORCID to a member profile, then run this command again.")
        return 0

    client = OpenAlexClient(os.environ.get("OPENALEX_EMAIL", ""))
    resolved: dict[str, str] = {}
    member_author_ids: dict[str, str] = {}
    for member in members:
        try:
            author = client.resolve_author(member.orcid)
        except RuntimeError as error:
            print(f"warning: could not resolve {member.name} ({member.orcid}): {error}", file=sys.stderr)
            continue
        author_id = str(author.get("id", "")).rsplit("/", 1)[-1]
        if not author_id:
            print(f"warning: OpenAlex has no author for {member.name} ({member.orcid})", file=sys.stderr)
            continue
        resolved[author_id] = member.name
        member_author_ids[member.name] = author_id
        print(f"Resolved {member.name}: {author_id}")

    works: dict[str, dict[str, Any]] = {}
    provenance: dict[str, set[str]] = {}
    for member in members:
        author_id = member_author_ids.get(member.name)
        if not author_id:
            continue
        print(f"Fetching works for {member.name} since {args.since}…")
        try:
            author_works = client.works(author_id, args.since)
            for work in author_works:
                if not args.include_all_types and work.get("type") not in ALLOWED_TYPES:
                    continue
                key = work_key(work)
                if not key:
                    continue
                works[key] = work
                provenance.setdefault(key, set()).add(member.name)
        except RuntimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    args.output.mkdir(parents=True, exist_ok=True)
    changed = 0
    expected: set[Path] = set()
    for key, work in works.items():
        path = output_path(args.output, work)
        expected.add(path)
        matches = group_authors(work, resolved) or sorted(provenance[key])
        content = render(work, matches)
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        if previous == content:
            continue
        action = "Would write" if args.dry_run else "Writing"
        print(f"{action} {path}")
        if not args.dry_run:
            path.write_text(content, encoding="utf-8")
        changed += 1

    removed = 0
    if args.prune:
        for path in args.output.glob("*.md"):
            if path not in expected and is_generated(path):
                action = "Would remove" if args.dry_run else "Removing"
                print(f"{action} {path}")
                if not args.dry_run:
                    path.unlink()
                removed += 1

    print(f"Found {len(works)} unique papers; {changed} changed, {removed} removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
