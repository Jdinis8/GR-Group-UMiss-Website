import tempfile
import unittest
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_publications as publications


SAMPLE_WORK = {
    "id": "https://openalex.org/W123456789",
    "doi": "https://doi.org/10.1234/example",
    "display_name": "A Test of Strong-Field Gravity",
    "publication_year": 2026,
    "publication_date": "2026-05-10",
    "type": "article",
    "authorships": [
        {"author": {"id": "https://openalex.org/A100", "display_name": "Ada Ray"}},
        {"author": {"id": "https://openalex.org/A200", "display_name": "Ben Wave"}},
    ],
    "primary_location": {"source": {"display_name": "Physical Review D"}},
    "best_oa_location": {"pdf_url": "https://example.test/paper.pdf"},
    "locations": [{"landing_page_url": "https://arxiv.org/abs/2605.01234"}],
    "ids": {},
    "biblio": {"volume": "111", "issue": "4", "first_page": "044001"},
}


class PublicationImporterTests(unittest.TestCase):
    def test_finds_only_published_profiles_with_valid_orcids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ada.md").write_text(
                "---\nname: Ada Ray\norcid: 0000-0002-1825-0097\n---\n", encoding="utf-8"
            )
            (root / "draft.md").write_text(
                "---\nname: Draft\npublished: false\norcid: 0000-0002-1825-0097\n---\n", encoding="utf-8"
            )
            members = publications.find_members(root)
            self.assertEqual([(member.name, member.orcid) for member in members], [("Ada Ray", "0000-0002-1825-0097")])

    def test_profile_can_use_openalex_id_without_orcid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ada.md").write_text(
                "---\nname: Ada Ray\nopenalex_id: A123456789\n---\n", encoding="utf-8"
            )
            members = publications.find_members(root)
            self.assertEqual([(member.name, member.openalex_id) for member in members], [("Ada Ray", "A123456789")])

    def test_profile_can_filter_ambiguous_openalex_record_through_orcid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ada.md").write_text(
                "---\nname: Ada Ray\norcid: 0000-0002-1825-0097\n"
                "openalex_id: A123456789\npublication_filter: orcid\n---\n",
                encoding="utf-8",
            )
            member = publications.find_members(root)[0]
        self.assertEqual(member.publication_filter, "orcid")

    def test_profile_can_filter_ambiguous_openalex_record_by_physics_topic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ada.md").write_text(
                "---\nname: Ada Ray\nopenalex_id: A123456789\n"
                "publication_filter: physics\n---\n",
                encoding="utf-8",
            )
            member = publications.find_members(root)[0]
            self.assertEqual(member.publication_filter, "physics")

    def test_profile_can_explicitly_include_a_misclassified_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ada.md").write_text(
                "---\nname: Ada Ray\nopenalex_id: A123456789\n"
                "publication_filter: physics\npublication_include: W123456789\n---\n",
                encoding="utf-8",
            )
            member = publications.find_members(root)[0]
            self.assertEqual(member.publication_include, frozenset({"W123456789"}))

    def test_orcid_allowlist_matches_ids_and_titles_but_rejects_unverified_work(self):
        payload = {
            "group": [
                {
                    "external-ids": {
                        "external-id": [
                            {
                                "external-id-type": "doi",
                                "external-id-value": "https://doi.org/10.1234/EXAMPLE",
                            },
                            {
                                "external-id-type": "arxiv",
                                "external-id-normalized": {"value": "arXiv:2605.01234"},
                            },
                        ]
                    },
                    "work-summary": [
                        {"title": {"title": {"value": "A Test of Strong-Field Gravity"}}}
                    ],
                }
            ]
        }
        allowlist = publications.orcid_work_allowlist(payload)
        self.assertTrue(publications.work_is_allowlisted(SAMPLE_WORK, allowlist))

        title_match = copy.deepcopy(SAMPLE_WORK)
        title_match["doi"] = "https://doi.org/10.9999/different"
        title_match["locations"] = []
        self.assertTrue(publications.work_is_allowlisted(title_match, allowlist))

        unrelated = copy.deepcopy(title_match)
        unrelated["display_name"] = "An Unrelated Detector Paper"
        self.assertFalse(publications.work_is_allowlisted(unrelated, allowlist))

    def test_physics_filter_uses_openalex_field(self):
        physics = copy.deepcopy(SAMPLE_WORK)
        physics["primary_topic"] = {
            "field": {
                "id": "https://openalex.org/fields/31",
                "display_name": "Physics and Astronomy",
            }
        }
        medicine = copy.deepcopy(SAMPLE_WORK)
        medicine["primary_topic"] = {
            "field": {
                "id": "https://openalex.org/fields/27",
                "display_name": "Medicine",
            }
        }
        self.assertTrue(publications.work_is_physics(physics))
        self.assertFalse(publications.work_is_physics(medicine))

    def test_placeholder_titles_and_publisher_notes_are_rejected(self):
        self.assertFalse(publications.has_meaningful_title({"display_name": "Untitled"}))
        self.assertFalse(
            publications.has_meaningful_title(
                {"display_name": "Publisher’s Note: A Test of Strong-Field Gravity"}
            )
        )
        self.assertTrue(publications.has_meaningful_title(SAMPLE_WORK))

    def test_render_contains_normalized_metadata(self):
        rendered = publications.render(SAMPLE_WORK, ["Ada Ray"])
        self.assertIn('doi: "10.1234/example"', rendered)
        self.assertIn('arxiv: "2605.01234"', rendered)
        self.assertIn('venue: "Physical Review D"', rendered)
        self.assertIn('group_authors: ["Ada Ray"]', rendered)

    def test_work_key_prefers_doi(self):
        self.assertEqual(publications.work_key(SAMPLE_WORK), "doi:10.1234/example")

    def test_work_key_deduplicates_doi_less_records_by_title_and_year(self):
        without_doi = dict(SAMPLE_WORK, doi=None)
        duplicate = dict(without_doi, id="https://openalex.org/W999999999")
        self.assertEqual(publications.work_key(without_doi), publications.work_key(duplicate))

    def test_output_path_is_stable_after_title_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = publications.output_path(root, SAMPLE_WORK)
            first.touch()
            changed = dict(SAMPLE_WORK, display_name="A Corrected Title")
            self.assertEqual(publications.output_path(root, changed), first)

    def test_deduplication_prefers_journal_record_and_keeps_arxiv(self):
        journal = copy.deepcopy(SAMPLE_WORK)
        journal["best_oa_location"] = {"landing_page_url": "https://doi.org/10.1234/example"}
        journal["locations"] = []
        preprint = copy.deepcopy(SAMPLE_WORK)
        preprint.update(
            {
                "id": "https://openalex.org/W987654321",
                "doi": "https://doi.org/10.48550/ARXIV.2605.01234",
                "display_name": "A TEST of strong field gravity!",
                "publication_date": "2025-11-01",
                "publication_year": 2025,
                "type": "preprint",
                "primary_location": {"source": {"display_name": "arXiv"}},
                "best_oa_location": {
                    "landing_page_url": "https://arxiv.org/abs/2605.01234",
                    "pdf_url": "https://arxiv.org/pdf/2605.01234",
                },
                "locations": [
                    {
                        "landing_page_url": "https://arxiv.org/abs/2605.01234",
                        "pdf_url": "https://arxiv.org/pdf/2605.01234",
                    }
                ],
                "ids": {"arxiv": "https://arxiv.org/abs/2605.01234"},
            }
        )
        works = {publications.work_key(journal): journal, publications.work_key(preprint): preprint}
        provenance = {key: {"Ada Ray"} for key in works}
        merged, _ = publications.deduplicate_works(works, provenance)
        self.assertEqual(len(merged), 1)
        record = next(iter(merged.values()))
        self.assertEqual(publications.clean_doi(record["doi"]), "10.1234/example")
        self.assertEqual(publications.arxiv_id(record), "2605.01234")
        self.assertEqual(record["best_oa_location"]["pdf_url"], "https://arxiv.org/pdf/2605.01234")

    def test_same_title_records_with_a_shared_author_are_merged(self):
        first = copy.deepcopy(SAMPLE_WORK)
        second = copy.deepcopy(SAMPLE_WORK)
        first["ids"] = {}
        first["locations"] = []
        second["id"] = "https://openalex.org/W111111111"
        second["doi"] = "https://doi.org/10.5678/different"
        second["ids"] = {}
        second["locations"] = []
        works = {publications.work_key(first): first, publications.work_key(second): second}
        provenance = {key: {"Ada Ray"} for key in works}
        merged, _ = publications.deduplicate_works(works, provenance)
        self.assertEqual(len(merged), 1)

    def test_distinct_papers_with_same_title_and_different_authors_are_not_merged(self):
        first = copy.deepcopy(SAMPLE_WORK)
        second = copy.deepcopy(SAMPLE_WORK)
        first["ids"] = {}
        first["locations"] = []
        second["id"] = "https://openalex.org/W111111111"
        second["doi"] = "https://doi.org/10.5678/different"
        second["ids"] = {}
        second["locations"] = []
        second["authorships"] = [
            {"author": {"id": "https://openalex.org/A300", "display_name": "Cara Lens"}}
        ]
        works = {publications.work_key(first): first, publications.work_key(second): second}
        provenance = {key: {"Ada Ray"} for key in works}
        merged, _ = publications.deduplicate_works(works, provenance)
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
