"""Exports must remain readable and valid with Unicode and BibTeX metacharacters."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from club.models import Paper, ReadingCard


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = get_user_model().objects.create_user("exporter", password="Research-Club!42")
        cls.paper = Paper.objects.create(
            title="中文 & 研究_{v2}：50% #1",
            authors="张三 and Alice Smith",
            year=2024,
            abstract="导出需要保留原始文字。",
            tags="研究方法",
            paper_url="https://example.org/paper?x=1&y=2",
            doi="",
            created_by=author,
        )
        cls.card = ReadingCard.objects.create(
            paper=cls.paper,
            author=author,
            research_question="中文研究问题",
            method="包含 Unicode：α、β 和中文",
            results="结果保留 50% 这样的符号。",
            limitations="没有 DOI 也可导出。",
            reflection="逐项核对原文。",
            discussion="",
            is_demo=True,
        )

    def test_markdown_export_contains_all_card_sections(self):
        response = self.client.get(reverse("club:card_markdown", args=[self.card.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn(f'card-{self.card.pk}.md', response["Content-Disposition"])
        self.assertIn("attachment", response["Content-Disposition"])
        exported = response.content.decode("utf-8")
        for value in (self.paper.title, self.card.research_question, self.card.method,
                      self.card.results, self.card.limitations, self.card.reflection):
            with self.subTest(value=value):
                self.assertIn(value, exported)
        self.assertIn("演示", exported)

    def test_bibtex_export_preserves_unicode_and_escapes_special_characters(self):
        response = self.client.get(reverse("club:paper_bibtex", args=[self.paper.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/x-bibtex; charset=utf-8")
        self.assertIn(f"paper-{self.paper.pk}.bib", response["Content-Disposition"])
        self.assertIn("attachment", response["Content-Disposition"])
        exported = response.content.decode("utf-8")
        self.assertIn("中文", exported)
        self.assertIn("张三", exported)
        for escaped in (r"\&", r"\_", r"\{", r"\}", r"\%", r"\#"):
            with self.subTest(escaped=escaped):
                self.assertIn(escaped, exported)
        self.assertNotRegex(exported, r"(?im)^\s*doi\s*=")
        self.assertIn("2024", exported)

    def test_optional_doi_is_included_when_present(self):
        self.paper.doi = "10.1234/test.2024"
        self.paper.save(update_fields=["doi"])
        response = self.client.get(reverse("club:paper_bibtex", args=[self.paper.pk]))
        self.assertIn("10.1234/test.2024", response.content.decode("utf-8"))
