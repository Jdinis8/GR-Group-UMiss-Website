import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
