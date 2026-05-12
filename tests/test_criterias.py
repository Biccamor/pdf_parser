"""Testy jednostkowe dla modułu criterias — heurystyki detekcji skanów PDF."""

import pytest

from criterias import delete_others_unicode, has_too_many_images, is_scanned_pdf


# ─── delete_others_unicode ───────────────────────────────────────────

class TestDeleteOthersUnicode:
    """Testy usuwania znaków kontrolnych Unicode."""

    def test_preserves_normal_text(self):
        assert delete_others_unicode("Hello World") == "Hello World"

    def test_preserves_newline_and_tab(self):
        assert delete_others_unicode("line1\nline2\tcol") == "line1\nline2\tcol"

    def test_removes_null_byte(self):
        assert delete_others_unicode("abc\x00def") == "abcdef"

    def test_removes_control_chars(self):
        """Znaki jak BEL (\x07), BS (\x08), ESC (\x1b) powinny zostać usunięte."""
        assert delete_others_unicode("a\x07b\x08c\x1bd") == "abcd"

    def test_preserves_polish_chars(self):
        assert delete_others_unicode("zażółć gęślą jaźń") == "zażółć gęślą jaźń"

    def test_empty_string(self):
        assert delete_others_unicode("") == ""

    def test_only_control_chars(self):
        assert delete_others_unicode("\x00\x01\x02\x03") == ""

    def test_mixed_content(self):
        result = delete_others_unicode("Name:\x00 Jan\x07\nSkills:\ttesting\x1b")
        assert result == "Name: Jan\nSkills:\ttesting"


# ─── is_scanned_pdf ─────────────────────────────────────────────────

class TestIsScannedPdf:
    """Testy detekcji czy PDF jest skanem (mało tekstu na stronę)."""

    def test_scanned_empty_text(self):
        """Pusty tekst → na pewno skan."""
        assert is_scanned_pdf("", page_count=1) is True

    def test_scanned_whitespace_only(self):
        """Same białe znaki → skan."""
        assert is_scanned_pdf("   \n\t  ", page_count=1) is True

    def test_scanned_very_little_text(self):
        """50 znaków na 1 stronę → poniżej progu 100 → skan."""
        assert is_scanned_pdf("x" * 50, page_count=1) is True

    def test_digital_enough_text(self):
        """200 znaków na 1 stronę → powyżej progu → cyfrowy."""
        assert is_scanned_pdf("a" * 200, page_count=1) is False

    def test_digital_exactly_at_threshold(self):
        """Dokładnie 100 znaków na stronę → na granicy → cyfrowy (nie <)."""
        assert is_scanned_pdf("b" * 100, page_count=1) is False

    def test_scanned_just_below_threshold(self):
        """99 znaków na stronę → poniżej progu."""
        assert is_scanned_pdf("c" * 99, page_count=1) is True

    def test_multipage_scanned(self):
        """150 znaków na 2 strony (próg = 200) → skan."""
        assert is_scanned_pdf("d" * 150, page_count=2) is True

    def test_multipage_digital(self):
        """500 znaków na 2 strony (próg = 200) → cyfrowy."""
        assert is_scanned_pdf("e" * 500, page_count=2) is False

    def test_custom_threshold(self):
        """Custom chars_per_page=50 — 60 znaków wystarczy."""
        assert is_scanned_pdf("f" * 60, page_count=1, chars_per_page=50) is False

    def test_custom_threshold_below(self):
        """Custom chars_per_page=200 — 150 znaków to za mało."""
        assert is_scanned_pdf("g" * 150, page_count=1, chars_per_page=200) is True

    def test_strips_whitespace_before_check(self):
        """Whitespace na brzegach nie liczy się do długości."""
        text = "  " + "h" * 80 + "  \n\n"  # 80 non-whitespace chars
        assert is_scanned_pdf(text, page_count=1) is True

    def test_realistic_cv_text(self):
        """Realistyczny tekst CV — powinien być wykryty jako cyfrowy."""
        cv_text = (
            "Education\n"
            "Warsaw University of Technology - Computer Science (2018-2023)\n"
            "Experience\n"
            "Junior Developer at Google (2023-2024)\n"
            "Skills\n"
            "Python, SQL, Docker, Kubernetes\n"
        )
        assert is_scanned_pdf(cv_text, page_count=1) is False

    def test_scanned_due_to_images(self):
        """Dużo tekstu ale za dużo tagów obrazkowych → skan (images heuristic)."""
        # 20 słów + 3 picture tagi = ratio 3/20 = 0.15 > 0.1
        text = "word " * 20 + "picture [ picture [ picture ["
        assert is_scanned_pdf(text, page_count=1) is True

    def test_digital_with_few_images(self):
        """Dużo tekstu i mało obrazków → cyfrowy."""
        text = "word " * 100 + "picture ["
        assert is_scanned_pdf(text, page_count=1) is False


# ─── has_too_many_images ────────────────────────────────────────────

class TestHasTooManyImages:
    """Testy detekcji nadmiarowych tagów obrazkowych."""

    def test_high_ratio_returns_true(self):
        """3 obrazki na 20 słów (15%) → za dużo."""
        text = "word " * 20 + "picture [ picture [ picture ["
        assert has_too_many_images(text) is True

    def test_low_ratio_returns_false(self):
        """1 obrazek na 100 słów (1%) → ok."""
        text = "word " * 100 + "picture ["
        assert has_too_many_images(text) is False

    def test_no_images_returns_false(self):
        """Brak tagów obrazkowych → ok."""
        text = "word " * 50
        assert has_too_many_images(text) is False

    def test_empty_text_returns_false(self):
        """Pusty tekst → False (poniżej min_words)."""
        assert has_too_many_images("") is False

    def test_below_min_words_skips_check(self):
        """Mało słów (< min_words) → pomija check, zwraca False.
        Chroni przed fałszywymi alarmami na krótkim tekście."""
        # 5 słów + 1 picture tag = ratio 1/6 = 16%, ale za mało słów
        text = "word " * 5 + "picture ["
        assert has_too_many_images(text) is False

    def test_exactly_at_min_words(self):
        """Dokładnie min_words słów → check działa."""
        # 10 słów + 2 picture tagi = 12 słów total, ratio 2/12 = 0.17 > 0.1
        text = "word " * 10 + "picture [ picture ["
        assert has_too_many_images(text) is True

    def test_custom_threshold(self):
        """Wyższy threshold — ratio 10% nie triggeruje przy progu 0.2."""
        # 20 słów + 2 picture tagi = 22 słowa, ratio 2/22 = 0.09
        text = "word " * 20 + "picture [ picture ["
        assert has_too_many_images(text, threshold=0.2) is False

    def test_custom_min_words(self):
        """Niższy min_words — check włącza się wcześniej."""
        # 3 słowa + 1 picture = 4 słowa, ratio 1/4 = 0.25
        text = "word " * 3 + "picture ["
        assert has_too_many_images(text, min_words=3) is True
