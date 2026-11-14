import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from club.curation import AI_NOTICE, CURATOR_NAME
from club.models import Comment, ImportedPaper, Paper, ReadingCard


def fixture(key="sample-source", title="真实论文导入测试"):
    return {
        "key": key,
        "paper": {"title": title, "authors": "Reader One; Reader Two", "year": 2026,
                  "abstract": "原文摘要要点（中文整理）：用于验证可重建的导读导入流程。",
                  "tags": "原文导读,测试", "paper_url": "https://example.org/" + key,
                  "doi": "10.1234/" + key, "code_url": ""},
        "card": {name: "【原文依据】PDF 第 1 页；用于检验导入。" for name in
                 ("research_question", "method", "results", "limitations", "reflection", "discussion")},
        "provenance": {"pdf_filename": "local-paper.pdf", "pdf_pages": 2, "reading_basis": "全文",
                       "publication": "Example Journal 2026", "publication_year": 2026,
                       "preprint_year": None, "metadata_sources": [{"label": "出版方", "url": "https://example.org/publisher"}],
                       "verification_notes": ["预印本年份未核实。"],
                       "evidence": [{"claim": "关键结论", "location": "PDF 第 1 页，表 1", "detail": "有明确条件的实验。"}]},
    }


class CuratedImportTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.data = fixture()
        self.write(self.data)

    def write(self, data, filename="sample.json"):
        (self.directory / filename).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def run_import(self):
        call_command("import_papers", data_dir=self.directory, stdout=io.StringIO())

    def test_repeat_is_idempotent_and_curator_cannot_log_in(self):
        self.run_import()
        first_ids = (Paper.objects.get().pk, ReadingCard.objects.get().pk)
        self.run_import()
        self.assertEqual((Paper.objects.count(), ReadingCard.objects.count(), ImportedPaper.objects.count()), (1, 1, 1))
        self.assertEqual(first_ids, (Paper.objects.get().pk, ReadingCard.objects.get().pk))
        self.assertFalse(get_user_model().objects.get(username=CURATOR_NAME).has_usable_password())
        self.assertEqual(Comment.objects.count(), 0)

    def test_reuses_doi_and_preserves_existing_metadata_and_cards(self):
        user = get_user_model().objects.create_user("student", password="safe-pass-223")
        fields = dict(self.data["paper"], title="学生维护的标题", paper_url="https://example.org/old")
        paper = Paper.objects.create(created_by=user, **fields)
        card = ReadingCard.objects.create(paper=paper, author=user, **self.data["card"])
        self.run_import()
        self.assertEqual(Paper.objects.count(), 1)
        paper.refresh_from_db()
        self.assertEqual(paper.title, "学生维护的标题")
        self.assertEqual(paper.created_by, user)
        self.assertTrue(ReadingCard.objects.filter(pk=card.pk, author=user).exists())
        self.assertEqual(ReadingCard.objects.filter(paper=paper).count(), 2)

    def test_manual_edits_survive_while_unchanged_fields_can_update(self):
        self.run_import()
        source = ImportedPaper.objects.get()
        Paper.objects.filter(pk=source.paper_id).update(title="人工修改标题")
        ReadingCard.objects.filter(pk=source.card_id).update(reflection="人工写下的理解")
        changed = copy.deepcopy(self.data)
        changed["paper"]["title"] = "新版原文标题"
        changed["paper"]["abstract"] = "新版摘要"
        changed["card"]["reflection"] = "新版机器理解"
        changed["card"]["method"] = "新版方法说明，PDF 第 2 页。"
        self.write(changed)
        self.run_import()
        source.refresh_from_db()
        self.assertEqual(source.paper.title, "人工修改标题")
        self.assertEqual(source.paper.abstract, "新版摘要")
        self.assertEqual(source.card.reflection, "人工写下的理解")
        self.assertEqual(source.card.method, "新版方法说明，PDF 第 2 页。")
        self.run_import()
        self.assertEqual(Paper.objects.count(), 1)

    def test_invalid_file_writes_nothing(self):
        second = fixture("bad-source")
        second["paper"]["year"] = "invalid"
        self.write(second, "z-bad.json")
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(Paper.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(username=CURATOR_NAME).exists())

    def test_account_collision_rolls_back(self):
        get_user_model().objects.create_user(CURATOR_NAME, password="student-private-password")
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(ImportedPaper.objects.count(), 0)

    def test_ambiguous_matching_does_not_pick_an_arbitrary_paper(self):
        user = get_user_model().objects.create_user("student")
        for _ in range(2):
            Paper.objects.create(created_by=user, **self.data["paper"])
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(ImportedPaper.objects.count(), 0)

    def test_source_notice_evidence_and_downloads_are_visible(self):
        self.run_import()
        source = ImportedPaper.objects.get()
        for name, pk in (("paper_detail", source.paper_id), ("card_detail", source.card_id)):
            response = self.client.get(reverse("club:" + name, args=[pk]))
            self.assertContains(response, AI_NOTICE)
            self.assertContains(response, "PDF 第 1 页，表 1")
            self.assertContains(response, "预印本年份")
        response = self.client.get(reverse("club:card_markdown", args=[source.card_id]))
        text = response.content.decode("utf-8")
        self.assertIn(AI_NOTICE, text)
        self.assertIn("PDF 第 1 页，表 1", text)
        self.assertIn("https://example.org/publisher", text)
        response = self.client.get(reverse("club:paper_bibtex", args=[source.paper_id]))
        self.assertIn("Example Journal 2026", response.content.decode("utf-8"))

    def test_curated_papers_stay_first_even_after_a_new_manual_paper(self):
        self.run_import()
        user = get_user_model().objects.create_user("new-student")
        newer = dict(self.data["paper"], title="后来录入的论文", doi="", paper_url="https://example.org/new")
        Paper.objects.create(created_by=user, **newer)
        response = self.client.get(reverse("club:paper_list"))
        self.assertEqual(response.context["papers"][0].pk, ImportedPaper.objects.get().paper_id)
        self.assertContains(response, "本期共读")


class BundledPaperImportTests(TestCase):
    def test_three_shipped_papers_rebuild_and_export_from_a_clean_database(self):
        call_command("import_papers", stdout=io.StringIO())
        first = list(ImportedPaper.objects.values_list("source_key", "paper_id", "card_id"))
        call_command("import_papers", stdout=io.StringIO())
        self.assertEqual(first, list(ImportedPaper.objects.values_list("source_key", "paper_id", "card_id")))
        self.assertEqual((Paper.objects.count(), ReadingCard.objects.count(), ImportedPaper.objects.count()), (3, 3, 3))
        for source in ImportedPaper.objects.select_related("paper", "card"):
            self.assertTrue(source.paper.doi.startswith("10.1109/"))
            self.assertIn(source.provenance["pdf_pages"], (11, 12, 14))
            self.assertTrue(source.provenance["evidence"])
            for route, pk in (("paper_detail", source.paper_id), ("card_detail", source.card_id)):
                self.assertContains(self.client.get(reverse("club:" + route, args=[pk])), AI_NOTICE)
            md = self.client.get(reverse("club:card_markdown", args=[source.card_id])).content.decode("utf-8")
            self.assertIn(AI_NOTICE, md)
            self.assertIn(source.paper.doi, md)
            bib = self.client.get(reverse("club:paper_bibtex", args=[source.paper_id])).content.decode("utf-8")
            self.assertIn(source.paper.doi, bib)
        listing = self.client.get(reverse("club:paper_list"))
        self.assertEqual([p.featured_priority for p in listing.context["papers"]], [30, 20, 10])
