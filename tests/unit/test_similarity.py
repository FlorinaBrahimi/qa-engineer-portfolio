"""Unit tests for the scoring logic and validation, independent of HTTP."""
import pytest

from app.server import MIN_TEXT_LENGTH, build_submission, validate
from app.similarity import KNOWN_CORPUS, similarity_band, similarity_score, word_count

pytestmark = [pytest.mark.regression]


class TestWordCount:
    @pytest.mark.parametrize("text, expected", [("", 0), ("one", 1), ("one two  three", 3), ("don't stop", 2), ("a1 b2, c3!", 3)])
    def test_counts_tokens(self, text, expected):
        assert word_count(text) == expected


class TestSimilarityScore:
    def test_empty_text_scores_zero(self):
        assert similarity_score("") == 0.0

    @pytest.mark.parametrize("doc", KNOWN_CORPUS)
    def test_every_corpus_document_scores_100(self, doc):
        assert similarity_score(doc) == 100.0

    def test_case_and_punctuation_are_ignored(self):
        assert similarity_score(KNOWN_CORPUS[0].upper() + "!!!") == 100.0

    def test_unrelated_text_scores_zero(self):
        assert similarity_score("completely original words that never appear together in the corpus") == 0.0

    def test_short_text_under_shingle_size_still_scores(self):
        assert 0.0 <= similarity_score("two words") <= 100.0

    def test_score_is_rounded_to_one_decimal(self):
        score = similarity_score(KNOWN_CORPUS[1] + " and some extra original words here")
        assert score == round(score, 1)


class TestSimilarityBand:
    @pytest.mark.parametrize(
        "score, band",
        [(0.0, "blue"), (0.1, "green"), (24.9, "green"), (25.0, "yellow"), (49.9, "yellow"), (50.0, "orange"), (74.9, "orange"), (75.0, "red"), (100.0, "red")],
    )
    def test_band_boundaries(self, score, band):
        assert similarity_band(score) == band


class TestValidate:
    def test_valid_payload_has_no_errors(self):
        assert validate({"title": "t", "author": "a", "text": "x" * MIN_TEXT_LENGTH}) == {}

    @pytest.mark.parametrize("field", ["title", "author", "text"])
    def test_missing_field_is_reported(self, field):
        payload = {"title": "t", "author": "a", "text": "x" * 30}
        payload.pop(field)
        assert field in validate(payload)

    def test_whitespace_only_text_fails_length_check(self):
        assert "text" in validate({"title": "t", "author": "a", "text": " " * 50})


class TestBuildSubmission:
    def test_status_flagged_at_threshold(self):
        sub = build_submission({"title": "t", "author": "a", "text": KNOWN_CORPUS[2]})
        assert sub["status"] == "flagged" and sub["similarity_score"] == 100.0

    def test_ids_are_unique(self):
        payload = {"title": "t", "author": "a", "text": "x" * 30}
        assert build_submission(payload)["id"] != build_submission(payload)["id"]
