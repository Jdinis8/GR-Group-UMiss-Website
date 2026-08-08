#!/usr/bin/env python3
"""Build Jekyll publication files from identifiers in _people/*.md.

The script uses only Python's standard library. It fetches works from OpenAlex
and, when a profile has an INSPIRE author link, INSPIRE. It de-duplicates the
combined records and writes machine-managed Markdown files to _publications/.
Hand-authored files are never overwritten.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

API_ROOT = "https://api.openalex.org"
ORCID_API_ROOT = "https://pub.orcid.org/v3.0"
INSPIRE_API_ROOT = "https://inspirehep.net/api"
ALLOWED_TYPES = {"article", "preprint", "book-chapter", "review"}
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


@dataclass(frozen=True)
class Member:
    name: str
    orcid: str
    openalex_id: str
    inspire_id: str
    publication_source: str
    publication_filter: str
    publication_include: frozenset[str]
    source: Path


@dataclass(frozen=True)
class WorkAllowlist:
    dois: frozenset[str]
    arxiv_ids: frozenset[str]
    titles: frozenset[str]


class OpenAlexClient:
    def __init__(self, email: str = "", pause: float = 0.1) -> None:
        self.email = email
        self.pause = pause

    def _request_json(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(url, headers=headers)
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
        raise RuntimeError(f"request failed for {url}: {last_error}")

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        if self.email:
            query["mailto"] = self.email
        url = f"{API_ROOT}/{path.lstrip('/')}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return self._request_json(
            url,
            {"Accept": "application/json", "User-Agent": "um-gravity-publications/1.0"},
        )

    def orcid_works(self, orcid: str) -> dict[str, Any]:
        url = f"{ORCID_API_ROOT}/{urllib.parse.quote(orcid)}/works"
        return self._request_json(
            url,
            {"Accept": "application/json", "User-Agent": "um-gravity-publications/1.0"},
        )

    def resolve_author(self, orcid: str) -> dict[str, Any]:
        return self.get(f"authors/https://orcid.org/{orcid}")

    def author(self, openalex_id: str) -> dict[str, Any]:
        return self.get(f"authors/{openalex_id}")

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
                        "open_access,primary_topic,topics"
                    ),
                },
            )
            yield from payload.get("results", [])
            cursor = payload.get("meta", {}).get("next_cursor")


class InspireClient:
    def __init__(self, pause: float = 0.1) -> None:
        self.pause = pause

    def _request_json(self, url: str) -> dict[str, Any]:
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
        raise RuntimeError(f"request failed for {url}: {last_error}")

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{INSPIRE_API_ROOT}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self._request_json(url)

    def works(self, inspire_id: str) -> Iterable[dict[str, Any]]:
        # A numeric profile URL is a stable author-record reference and covers
        # papers filed under older BAI/name variants. Raw BAI values still use
        # INSPIRE's author-search operator.
        query = (
            f"authors.record.$ref:{inspire_id}"
            if inspire_id.isdigit()
            else f"a {inspire_id}"
        )
        page = 1
        page_size = 100
        while True:
            payload = self.get(
                "literature",
                {"q": query, "size": str(page_size), "page": str(page)},
            )
            hits = (payload.get("hits") or {}).get("hits") or []
            yield from hits
            total = (payload.get("hits") or {}).get("total") or 0
            if isinstance(total, dict):
                total = total.get("value") or 0
            if not hits or page * page_size >= int(total):
                break
            page += 1


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


def inspire_author_id(value: str) -> str:
    """Accept either an INSPIRE author URL, numeric record ID, or BAI."""
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme or parsed.netloc:
        match = re.search(r"/authors/([^/]+)", parsed.path)
        return urllib.parse.unquote(match.group(1)) if match else ""
    return value


def find_members(directory: Path) -> list[Member]:
    members: list[Member] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        data = front_matter(path)
        if str(data.get("published", "true")).lower() == "false":
            continue
        orcid = str(data.get("orcid", "")).removeprefix("https://orcid.org/").strip()
        openalex_id = str(data.get("openalex_id", "")).removeprefix("https://openalex.org/").strip().upper()
        inspire_id = inspire_author_id(str(data.get("inspire", "")))
        if not orcid and not openalex_id and not inspire_id:
            continue
        if orcid and not ORCID_PATTERN.fullmatch(orcid):
            print(f"warning: invalid ORCID {orcid!r} in {path}", file=sys.stderr)
            continue
        if openalex_id and not re.fullmatch(r"A\d+", openalex_id):
            print(f"warning: invalid OpenAlex author ID {openalex_id!r} in {path}", file=sys.stderr)
            continue
        if inspire_id and not re.fullmatch(r"(?:\d+|[A-Za-z][A-Za-z0-9.-]+)", inspire_id):
            print(f"warning: invalid INSPIRE author ID {inspire_id!r} in {path}", file=sys.stderr)
            continue
        publication_source = str(data.get("publication_source", "openalex")).strip().casefold()
        if publication_source not in {"openalex", "inspire", "both"}:
            print(f"warning: invalid publication_source {publication_source!r} in {path}", file=sys.stderr)
            continue
        if publication_source in {"openalex", "both"} and not (orcid or openalex_id):
            print(f"warning: publication_source {publication_source!r} requires an ORCID or OpenAlex ID in {path}", file=sys.stderr)
            continue
        if publication_source in {"inspire", "both"} and not inspire_id:
            print(f"warning: publication_source {publication_source!r} requires an INSPIRE author link in {path}", file=sys.stderr)
            continue
        publication_filter = str(data.get("publication_filter", "")).strip().casefold()
        if publication_filter not in {"", "orcid", "physics"}:
            print(f"warning: invalid publication_filter {publication_filter!r} in {path}", file=sys.stderr)
            continue
        if publication_filter == "orcid" and not orcid:
            print(f"warning: publication_filter 'orcid' requires an ORCID in {path}", file=sys.stderr)
            continue
        include_value = str(data.get("publication_include", "")).upper()
        publication_include = frozenset(re.findall(r"W\d+", include_value))
        members.append(
            Member(
                str(data.get("name", path.stem)),
                orcid,
                openalex_id,
                inspire_id,
                publication_source,
                publication_filter,
                publication_include,
                path,
            )
        )
    return members


def clean_doi(value: str | None) -> str:
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value or "", flags=re.IGNORECASE)


def clean_arxiv_identifier(value: str | None) -> str:
    identifier = str(value or "").strip()
    identifier = re.sub(
        r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/", "", identifier, flags=re.IGNORECASE
    )
    identifier = re.sub(r"^arxiv:\s*", "", identifier, flags=re.IGNORECASE)
    identifier = re.sub(r"\.pdf$", "", identifier, flags=re.IGNORECASE)
    return re.sub(r"v\d+$", "", identifier, flags=re.IGNORECASE).casefold()


def arxiv_id(work: dict[str, Any]) -> str:
    doi = clean_doi(work.get("doi"))
    if doi.lower().startswith("10.48550/arxiv."):
        return re.sub(r"^10\.48550/arxiv\.", "", doi, flags=re.IGNORECASE)
    arxiv = str(work.get("ids", {}).get("arxiv", ""))
    if arxiv:
        return arxiv.removeprefix("https://arxiv.org/abs/")
    for location in work.get("locations") or []:
        landing = str(location.get("landing_page_url") or "")
        if "arxiv.org/abs/" in landing:
            return landing.split("arxiv.org/abs/", 1)[1]
    return ""


def normalize_title_value(value: Any) -> str:
    title = re.sub(r"<[^>]+>", "", html.unescape(str(value or "")))
    title = unicodedata.normalize("NFKD", title).casefold()
    return "".join(character for character in title if character.isalnum())


def has_meaningful_title(work: dict[str, Any]) -> bool:
    """Reject placeholder records and publisher notices rather than papers."""
    title = html.unescape(str(work.get("display_name") or work.get("title") or ""))
    title = re.sub(r"<[^>]+>", "", title).strip().casefold().replace("’", "'")
    if not title or title in {"untitled", "publication"}:
        return False
    return not re.match(r"^(?:publisher'?s note|erratum|corrigendum|correction)\b", title)


def openalex_work_id(work: dict[str, Any]) -> str:
    return str(work.get("id") or "").rstrip("/").rsplit("/", 1)[-1].upper()


def orcid_work_allowlist(payload: dict[str, Any]) -> WorkAllowlist:
    """Build stable identifiers from the works curated on an ORCID record."""
    dois: set[str] = set()
    arxiv_ids: set[str] = set()
    titles: set[str] = set()
    for group in payload.get("group") or []:
        external_ids = (group.get("external-ids") or {}).get("external-id") or []
        for external_id in external_ids:
            kind = str(external_id.get("external-id-type") or "").casefold()
            normalized = external_id.get("external-id-normalized") or {}
            value = str(normalized.get("value") or external_id.get("external-id-value") or "")
            if kind == "doi":
                doi = clean_doi(value).casefold()
                if doi:
                    dois.add(doi)
            elif kind == "arxiv":
                identifier = clean_arxiv_identifier(value)
                if identifier:
                    arxiv_ids.add(identifier)
        for summary in group.get("work-summary") or []:
            title = normalize_title_value(((summary.get("title") or {}).get("title") or {}).get("value"))
            if title:
                titles.add(title)
    return WorkAllowlist(frozenset(dois), frozenset(arxiv_ids), frozenset(titles))


def work_is_allowlisted(work: dict[str, Any], allowlist: WorkAllowlist) -> bool:
    doi = clean_doi(work.get("doi")).casefold()
    arxiv = clean_arxiv_identifier(arxiv_id(work))
    title = normalized_title(work)
    return bool(
        (doi and doi in allowlist.dois)
        or (arxiv and arxiv in allowlist.arxiv_ids)
        or (title and title in allowlist.titles)
    )


def work_is_physics(work: dict[str, Any]) -> bool:
    """Accept works classified by OpenAlex in Physics and Astronomy."""
    topics = [work.get("primary_topic") or {}, *(work.get("topics") or [])]
    for topic in topics:
        field = topic.get("field") or {}
        field_id = str(field.get("id") or "").rstrip("/").rsplit("/", 1)[-1]
        if field_id == "31" or str(field.get("display_name") or "").casefold() == "physics and astronomy":
            return True
    return False


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


def inspire_author_name(value: str) -> str:
    """Convert INSPIRE's 'Family, Given' names to the site's display order."""
    family, separator, given = str(value or "").partition(",")
    if not separator:
        return family.strip()
    return f"{given.strip()} {family.strip()}".strip()


def normalize_inspire_work(record: dict[str, Any]) -> dict[str, Any]:
    """Translate an INSPIRE literature hit into the importer's work schema."""
    metadata = record.get("metadata") or {}
    control_number = str(record.get("id") or metadata.get("control_number") or "")
    inspire_url = f"https://inspirehep.net/literature/{control_number}"

    titles = metadata.get("titles") or []
    title = str((titles[0] if titles else {}).get("title") or "")

    publication_info = metadata.get("publication_info") or []
    journal = next(
        (item for item in publication_info if item.get("material") == "publication"),
        publication_info[0] if publication_info else {},
    )
    imprints = metadata.get("imprints") or []
    date = str(
        (imprints[0] if imprints else {}).get("date")
        or metadata.get("preprint_date")
        or metadata.get("earliest_date")
        or ""
    )
    year = journal.get("year") or (date[:4] if date else "")
    if not date and year:
        date = f"{year}-01-01"

    dois = metadata.get("dois") or []
    preferred_doi = next(
        (item for item in dois if item.get("material") == "publication"),
        dois[0] if dois else {},
    )
    doi = str(preferred_doi.get("value") or "")

    arxiv_eprints = metadata.get("arxiv_eprints") or []
    arxiv = str((arxiv_eprints[0] if arxiv_eprints else {}).get("value") or "")
    arxiv_location = (
        {
            "landing_page_url": f"https://arxiv.org/abs/{arxiv}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv}",
            "source": {"display_name": "arXiv"},
        }
        if arxiv
        else {}
    )

    authorships = []
    for author in metadata.get("authors") or []:
        reference = str((author.get("record") or {}).get("$ref") or "")
        author_id = reference.replace("/api/authors/", "/authors/")
        authorships.append(
            {
                "author": {
                    "id": author_id,
                    "display_name": inspire_author_name(author.get("full_name") or ""),
                }
            }
        )

    document_types = [str(item).casefold() for item in metadata.get("document_type") or []]
    work_type = next((item for item in document_types if item in ALLOWED_TYPES), "")
    if not work_type and "book chapter" in document_types:
        work_type = "book-chapter"
    if not work_type and "conference paper" in document_types:
        work_type = "article"
    work_type = work_type or (document_types[0] if document_types else "article")

    venue = str(journal.get("journal_title") or ("arXiv" if arxiv else ""))
    ids = {"inspire": inspire_url}
    if arxiv:
        ids["arxiv"] = f"https://arxiv.org/abs/{arxiv}"

    return {
        "id": inspire_url,
        "doi": f"https://doi.org/{doi}" if doi else None,
        "display_name": title,
        "publication_year": int(year) if str(year).isdigit() else None,
        "publication_date": date,
        "type": work_type,
        "authorships": authorships,
        "primary_location": {"source": {"display_name": venue}} if venue else {},
        "best_oa_location": arxiv_location,
        "locations": [arxiv_location] if arxiv_location else [],
        "ids": ids,
        "biblio": {
            "volume": journal.get("journal_volume") or "",
            "issue": journal.get("journal_issue") or "",
            "first_page": journal.get("artid") or journal.get("page_start") or "",
        },
    }


def author_ids(work: dict[str, Any]) -> set[str]:
    """Return stable OpenAlex author IDs for duplicate comparisons."""
    return {
        str((authorship.get("author") or {}).get("id", "")).rsplit("/", 1)[-1]
        for authorship in work.get("authorships") or []
        if (authorship.get("author") or {}).get("id")
    }


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


def normalized_title(work: dict[str, Any]) -> str:
    """Return a case- and punctuation-insensitive title identity."""
    return normalize_title_value(work.get("display_name") or work.get("title") or "")


def is_arxiv_doi(doi: str | None) -> bool:
    return clean_doi(doi).lower().startswith("10.48550/arxiv.")


def is_preprint_like(work: dict[str, Any]) -> bool:
    """Identify preprint/repository records even when OpenAlex calls them articles."""
    doi = clean_doi(work.get("doi"))
    if doi and not is_arxiv_doi(doi):
        return False
    if work.get("type") == "preprint" or is_arxiv_doi(doi):
        return True
    venue = venue_name(work).casefold()
    return "arxiv" in venue


def publication_rank(work: dict[str, Any]) -> tuple[int, int, int, int, str]:
    """Rank records so a journal version wins over its preprint."""
    doi = clean_doi(work.get("doi"))
    published = not is_preprint_like(work) and (
        bool(doi) or work.get("type") in {"article", "review", "book-chapter"}
    )
    journal_doi = bool(doi) and not is_arxiv_doi(doi)
    venue = bool(venue_name(work)) and not is_preprint_like(work)
    metadata = sum(
        bool(work.get(field))
        for field in ("publication_date", "publication_year", "biblio", "best_oa_location")
    )
    date = str(work.get("publication_date") or "")
    return (int(published), int(journal_doi), int(venue), metadata, date)


def merge_work_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep the best bibliographic record and fill it with preprint metadata."""
    preferred = max(group, key=publication_rank)
    merged = copy.deepcopy(preferred)

    longest_authorships = max(
        (work.get("authorships") or [] for work in group), key=len, default=[]
    )
    if len(longest_authorships) > len(merged.get("authorships") or []):
        merged["authorships"] = copy.deepcopy(longest_authorships)

    locations: list[dict[str, Any]] = []
    seen_locations: set[tuple[str, str]] = set()
    for work in group:
        candidates = list(work.get("locations") or [])
        for key in ("primary_location", "best_oa_location"):
            if work.get(key):
                candidates.append(work[key])
        for location in candidates:
            identity = (
                str(location.get("landing_page_url") or ""),
                str(location.get("pdf_url") or ""),
            )
            if identity != ("", "") and identity not in seen_locations:
                locations.append(copy.deepcopy(location))
                seen_locations.add(identity)
    merged["locations"] = locations

    preprint_id = next((arxiv_id(work) for work in group if arxiv_id(work)), "")
    if preprint_id:
        merged.setdefault("ids", {})["arxiv"] = f"https://arxiv.org/abs/{preprint_id}"

    best_oa = merged.get("best_oa_location") or {}
    if not best_oa.get("pdf_url"):
        pdf_location = next(
            (
                location
                for location in locations
                if location.get("pdf_url") and "arxiv" in str(location.get("pdf_url")).casefold()
            ),
            None,
        ) or next((location for location in locations if location.get("pdf_url")), None)
        if pdf_location:
            merged["best_oa_location"] = copy.deepcopy(pdf_location)
    return merged


def deduplicate_works(
    works: dict[str, dict[str, Any]], provenance: dict[str, set[str]]
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    """Merge OpenAlex records representing the same preprint/journal paper.

    DOI and arXiv identities are always merged case-insensitively. Records with
    the same normalized title are also merged when they share an OpenAlex
    author, covering repository copies, versioned preprints, conference copies,
    and duplicate publisher records without conflating unrelated papers that
    happen to reuse a title.
    """
    entries = list(works.items())
    parent = list(range(len(entries)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    identities: dict[tuple[str, str], int] = {}
    title_groups: dict[str, list[int]] = {}
    for index, (_, work) in enumerate(entries):
        doi = clean_doi(work.get("doi")).casefold()
        arxiv = arxiv_id(work).casefold()
        for kind, value in (("doi", doi), ("arxiv", arxiv)):
            if not value:
                continue
            identity = (kind, value)
            if identity in identities:
                union(index, identities[identity])
            else:
                identities[identity] = index
        title = normalized_title(work)
        if title:
            title_groups.setdefault(title, []).append(index)

    for indexes in title_groups.values():
        for position, left in enumerate(indexes):
            left_authors = author_ids(entries[left][1])
            if not left_authors:
                continue
            for right in indexes[position + 1 :]:
                if left_authors.intersection(author_ids(entries[right][1])):
                    union(left, right)

    groups: dict[int, list[int]] = {}
    for index in range(len(entries)):
        groups.setdefault(find(index), []).append(index)

    deduplicated: dict[str, dict[str, Any]] = {}
    deduplicated_provenance: dict[str, set[str]] = {}
    for indexes in groups.values():
        group_works = [entries[index][1] for index in indexes]
        merged = merge_work_group(group_works)
        key = str(merged.get("id") or work_key(merged)).casefold()
        deduplicated[key] = merged
        members: set[str] = set()
        for index in indexes:
            members.update(provenance.get(entries[index][0], set()))
        deduplicated_provenance[key] = members
    return deduplicated, deduplicated_provenance


def slugify(value: str, limit: int = 58) -> str:
    value = value.encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:limit].rstrip("-") or "publication"


def yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render(work: dict[str, Any], matched_members: list[str]) -> str:
    names = author_names(work)
    work_url = str(work.get("id", ""))
    identifiers = work.get("ids") or {}
    openalex = str(identifiers.get("openalex") or "")
    if not openalex and "openalex.org/" in work_url:
        openalex = work_url
    inspire = str(identifiers.get("inspire") or "")
    if not inspire and "inspirehep.net/literature/" in work_url:
        inspire = work_url
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
    ]
    if inspire:
        lines.append(f"inspire: {yaml_string(inspire)}")
    lines.extend([
        f"pdf: {yaml_string(pdf or '')}",
        f"work_type: {yaml_string(work.get('type') or '')}",
        "---",
        "",
        "<!-- This file is maintained by scripts/fetch_publications.py. -->",
        "",
    ])
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
    parser.add_argument("--since", default="1980-01-01", help="earliest publication date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing files")
    parser.add_argument("--prune", action="store_true", help="remove generated files no longer returned by publication sources")
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
        print(f"No published profiles with valid publication identifiers found in {args.people}.")
        print("Add an ORCID, openalex_id, or inspire link to a profile, then run this command again.")
        return 0

    client = OpenAlexClient(os.environ.get("OPENALEX_EMAIL", ""))
    inspire_client = InspireClient()
    resolved: dict[str, str] = {}
    member_author_ids: dict[str, str] = {}
    for member in members:
        if member.publication_source not in {"openalex", "both"}:
            continue
        try:
            author = client.author(member.openalex_id) if member.openalex_id else client.resolve_author(member.orcid)
        except RuntimeError as error:
            identifier = member.openalex_id or member.orcid
            print(f"warning: could not resolve {member.name} ({identifier}): {error}", file=sys.stderr)
            continue
        author_id = str(author.get("id", "")).rsplit("/", 1)[-1]
        if not author_id:
            print(f"warning: OpenAlex has no author for {member.name}", file=sys.stderr)
            continue
        resolved[author_id] = member.name
        member_author_ids[member.name] = author_id
        print(f"Resolved {member.name}: {author_id}")

    works: dict[str, dict[str, Any]] = {}
    provenance: dict[str, set[str]] = {}
    for member in members:
        if member.publication_source not in {"openalex", "both"}:
            continue
        author_id = member_author_ids.get(member.name)
        if not author_id:
            continue
        allowlist: WorkAllowlist | None = None
        if member.publication_filter == "orcid":
            try:
                allowlist = orcid_work_allowlist(client.orcid_works(member.orcid))
            except RuntimeError as error:
                print(f"error: could not load ORCID works for {member.name}: {error}", file=sys.stderr)
                return 1
            print(f"Using the ORCID-curated works list to filter {member.name}.")
        elif member.publication_filter == "physics":
            print(f"Using OpenAlex Physics and Astronomy topics to filter {member.name}.")
        print(f"Fetching works for {member.name} since {args.since}…")
        filtered = 0
        try:
            author_works = client.works(author_id, args.since)
            for work in author_works:
                if not args.include_all_types and work.get("type") not in ALLOWED_TYPES:
                    continue
                if not has_meaningful_title(work):
                    filtered += 1
                    continue
                force_include = openalex_work_id(work) in member.publication_include
                if not force_include:
                    if allowlist is not None and not work_is_allowlisted(work, allowlist):
                        filtered += 1
                        continue
                    if member.publication_filter == "physics" and not work_is_physics(work):
                        filtered += 1
                        continue
                key = work_key(work)
                if not key:
                    continue
                works[key] = work
                provenance.setdefault(key, set()).add(member.name)
        except RuntimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        if filtered:
            print(f"Filtered {filtered} unverified OpenAlex works for {member.name}.")

    for member in members:
        if member.publication_source not in {"inspire", "both"}:
            continue
        print(f"Fetching INSPIRE works for {member.name} since {args.since}…")
        filtered = 0
        try:
            for record in inspire_client.works(member.inspire_id):
                work = normalize_inspire_work(record)
                publication_date = str(work.get("publication_date") or "")
                if publication_date and publication_date < args.since:
                    continue
                if not args.include_all_types and work.get("type") not in ALLOWED_TYPES:
                    continue
                if not has_meaningful_title(work):
                    filtered += 1
                    continue
                control_number = str(work.get("id") or "").rstrip("/").rsplit("/", 1)[-1]
                key = f"inspire:{control_number}"
                works[key] = work
                provenance.setdefault(key, set()).add(member.name)
        except RuntimeError as error:
            print(f"error: could not load INSPIRE works for {member.name}: {error}", file=sys.stderr)
            return 1
        if filtered:
            print(f"Filtered {filtered} invalid INSPIRE works for {member.name}.")

    raw_count = len(works)
    works, provenance = deduplicate_works(works, provenance)
    duplicate_count = raw_count - len(works)

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

    print(
        f"Found {len(works)} unique papers; merged {duplicate_count} duplicate records; "
        f"{changed} changed, {removed} removed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
