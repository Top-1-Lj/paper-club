"""The demo initializer is repeatable and leaves user-authored work intact."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase

from club.models import Comment, Paper, ReadingCard, ReadingProgress


class DemoSeedTests(TestCase):
    def seed(self):
        call_command("seed_demo", stdout=StringIO())

    def counts(self):
        return tuple(model.objects.count() for model in
                     (get_user_model(), Paper, ReadingCard, ReadingProgress, Comment))

    def test_seed_provides_multireader_demo_and_is_idempotent(self):
        self.seed()
        users = get_user_model().objects.filter(username__in=["lin", "chen"])
        self.assertEqual(users.count(), 2)
        for user in users:
            with self.subTest(user=user.username):
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertTrue(user.check_password("PaperClub2026!"))
                self.assertGreaterEqual(ReadingCard.objects.filter(author=user).count(), 4)
        self.assertGreaterEqual(Paper.objects.count(), 8)
        self.assertGreaterEqual(ReadingCard.objects.count(), 8)
        self.assertTrue(ReadingCard.objects.filter(is_demo=True).exists())
        self.assertTrue(Comment.objects.filter(is_demo=True).exists())
        before = self.counts()
        self.seed()
        self.assertEqual(self.counts(), before)

    def test_second_seed_keeps_user_edits_password_and_status(self):
        self.seed()
        lin = get_user_model().objects.get(username="lin")
        lin.set_password("My-New-Password!482")
        lin.save()
        card = ReadingCard.objects.filter(author=lin).first()
        card.reflection = "这是用户后来补充的阅读理解，初始化不应覆盖。"
        card.save()
        progress, _ = ReadingProgress.objects.get_or_create(paper=card.paper, user=lin)
        progress.status = "unread"
        progress.save()
        comment = Comment.objects.first()
        comment.content = "用户编辑后的评论也应保留。"
        comment.save()
        before = self.counts()
        self.seed()
        self.assertEqual(self.counts(), before)
        lin.refresh_from_db()
        card.refresh_from_db()
        comment.refresh_from_db()
        progress.refresh_from_db()
        self.assertTrue(lin.check_password("My-New-Password!482"))
        self.assertEqual(card.reflection, "这是用户后来补充的阅读理解，初始化不应覆盖。")
        self.assertEqual(comment.content, "用户编辑后的评论也应保留。")
        self.assertEqual(progress.status, "unread")

    def test_existing_unrelated_username_is_not_claimed_by_demo_seed(self):
        user = get_user_model().objects.create_user("lin", password="Existing-Account!42")
        with self.assertRaises(CommandError):
            self.seed()
        user.refresh_from_db()
        self.assertTrue(user.check_password("Existing-Account!42"))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(Paper.objects.count(), 0)
        self.assertEqual(ReadingCard.objects.count(), 0)

    def test_edited_demo_paper_url_keeps_identity_and_user_changes(self):
        self.seed()
        paper = Paper.objects.order_by("pk").first()
        original_key = paper.demo_key
        paper.title = "用户修订后的论文标题"
        paper.paper_url = "https://example.org/my-updated-paper"
        paper.save()
        before = self.counts()
        self.seed()
        self.assertEqual(self.counts(), before)
        paper.refresh_from_db()
        self.assertEqual(paper.demo_key, original_key)
        self.assertEqual(paper.title, "用户修订后的论文标题")
        self.assertEqual(paper.paper_url, "https://example.org/my-updated-paper")

    def test_legacy_demo_paper_receives_key_without_being_recreated(self):
        self.seed()
        paper = Paper.objects.order_by("pk").first()
        original_key = paper.demo_key
        paper.demo_key = None
        paper.title = "旧版演示论文的用户修订标题"
        paper.save()
        before = self.counts()
        self.seed()
        self.assertEqual(self.counts(), before)
        paper.refresh_from_db()
        self.assertEqual(paper.demo_key, original_key)
        self.assertEqual(paper.title, "旧版演示论文的用户修订标题")

    def test_ordinary_readers_same_source_url_is_not_claimed_as_demo(self):
        from club.management.commands.seed_demo import PAPERS

        reader = get_user_model().objects.create_user("reader", password="Independent-Reader!42")
        source_url = f"https://arxiv.org/abs/{PAPERS[0]['arxiv']}"
        ordinary_paper = Paper.objects.create(
            created_by=reader,
            title="普通读者自行录入的同源论文",
            authors="普通读者录入的作者",
            year=2024,
            abstract="这条记录属于普通读者，不能被初始化命令认领。",
            paper_url=source_url,
        )
        self.seed()
        ordinary_paper.refresh_from_db()
        self.assertIsNone(ordinary_paper.demo_key)
        self.assertEqual(ordinary_paper.created_by, reader)
        self.assertEqual(ordinary_paper.title, "普通读者自行录入的同源论文")
        self.assertEqual(Paper.objects.filter(paper_url=source_url).count(), 2)
        self.assertEqual(Paper.objects.filter(demo_key__isnull=False).count(), len(PAPERS))
        self.assertFalse(ReadingCard.objects.filter(paper=ordinary_paper).exists())
