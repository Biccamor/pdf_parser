"""Testy dla funkcji clean_cv_markdown z main.py."""

import pytest

from main import clean_cv_markdown


class TestCleanCvMarkdown:
    """Testy czyszczenia artefaktów markdown z parsowania PDF."""

    def test_removes_inline_backticks(self):
        assert clean_cv_markdown("`Python`") == "Python"

    def test_removes_multiple_backticks(self):
        assert clean_cv_markdown("`Python`, `SQL`, `Docker`") == "Python, SQL, Docker"

    def test_removes_markdown_header_with_bold(self):
        assert clean_cv_markdown("## **Skills**") == "Skills"

    def test_removes_markdown_header_without_bold(self):
        assert clean_cv_markdown("### Education") == "Education"

    def test_removes_h1_header(self):
        assert clean_cv_markdown("# Summary") == "Summary"

    def test_preserves_normal_text(self):
        text = "Junior Developer at Google (2023-2024)"
        assert clean_cv_markdown(text) == text

    def test_combined_backticks_and_headers(self):
        text = "## **Skills**\n`Python`, `SQL`\n### Experience"
        expected = "Skills\nPython, SQL\nExperience"
        assert clean_cv_markdown(text) == expected

    def test_empty_string(self):
        assert clean_cv_markdown("") == ""

    def test_multiline_with_mixed_content(self):
        text = "# **CV**\nName: Jan\n`Docker` experience\n## Education"
        result = clean_cv_markdown(text)
        assert "`" not in result
        assert "##" not in result
        assert "Name: Jan" in result

    def test_preserves_parentheses_and_dates(self):
        text = "Warsaw University (2018-2023)"
        assert clean_cv_markdown(text) == text

    def test_nested_bold_in_header(self):
        """Header z gwiazdkami bold powinien być wyczyszczony."""
        assert clean_cv_markdown("#### **Extra**") == "Extra"

    def test_removes_bold_from_body(self):
        """Bold w treści body powinien być usunięty."""
        assert clean_cv_markdown("Used **Python** and **Docker**") == "Used Python and Docker"

    def test_removes_italic_from_body(self):
        """Italic w treści body powinien być usunięty."""
        assert clean_cv_markdown("Used *Python* and *Docker*") == "Used Python and Docker"

    def test_removes_bold_tech_stack(self):
        """Typowy bold tech stack z CV PDF."""
        text = "**Scala | Swift | Lab Study | Pattern Detection**"
        expected = "Scala | Swift | Lab Study | Pattern Detection"
        assert clean_cv_markdown(text) == expected

    def test_removes_hashtag_tags(self):
        """Hashtag-tagi na końcu linii powinny być usunięte."""
        text = "Migrating to Scala 3 #Scala #Migration #Scala3"
        expected = "Migrating to Scala 3"
        assert clean_cv_markdown(text) == expected

    def test_preserves_text_without_hashtags(self):
        """Tekst bez hashtagów nie powinien być zmieniony."""
        text = "Built e-commerce platforms for 5+ clients"
        assert clean_cv_markdown(text) == text

    def test_hashtag_multiline(self):
        """Hashtagi usuwane z każdej linii osobno."""
        text = "Article about Scala #Scala #FP\nAnother post #Java"
        expected = "Article about Scala\nAnother post"
        assert clean_cv_markdown(text) == expected

