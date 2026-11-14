"""Exercise the public workflow, ownership checks, and per-reader state."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from club.models import Comment, Paper, ReadingCard, ReadingProgress


User = get_user_model()


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="Research-Club!42")
        cls.bob = User.objects.create_user("bob", password="Another-Reader!42")
        cls.paper = Paper.objects.create(
            title="Attention Is All You Need · 共读",
            authors="Ashish Vaswani et al.",
            year=2017,
            abstract="用注意力机制处理序列建模问题。",
            tags="自然语言处理,深度学习",
            paper_url="https://arxiv.org/abs/1706.03762",
            created_by=cls.alice,
        )
        cls.card = ReadingCard.objects.create(
            paper=cls.paper,
            author=cls.alice,
            research_question="如何建模序列中的长距离依赖？",
            method="使用多头自注意力。",
            results="比较不同翻译任务中的结果。",
            limitations="需要进一步评估长文本场景。",
            reflection="先理解机制，再验证结论。",
            discussion="位置编码有哪些选择？",
        )
        cls.comment = Comment.objects.create(
            card=cls.card, author=cls.bob, content="建议补充实验设置。"
        )

    def paper_data(self, **changes):
        data = {
            "title": "一篇新的共读论文",
            "authors": "张同学, 李同学",
            "year": 2024,
            "abstract": "这是一份用于验证录入流程的摘要。",
            "tags": "机器学习,可复现研究",
            "paper_url": "https://example.org/paper",
            "doi": "",
            "code_url": "",
        }
        data.update(changes)
        return data

    def card_data(self, **changes):
        data = {
            "research_question": "这个研究解决什么问题？",
            "method": "描述方法的关键步骤。",
            "results": "记录有依据的实验结果。",
            "limitations": "指出实验与方法的局限。",
            "reflection": "我对方法的理解与复现思路。",
            "discussion": "下一次共读想讨论的问题。",
            "status": "reading",
        }
        data.update(changes)
        return data

    def test_public_pages_and_exports_are_readable_without_login(self):
        routes = [
            ("paper_list", {}),
            ("paper_detail", {"pk": self.paper.pk}),
            ("card_detail", {"pk": self.card.pk}),
            ("paper_bibtex", {"pk": self.paper.pk}),
            ("card_markdown", {"pk": self.card.pk}),
        ]
        for name, kwargs in routes:
            with self.subTest(route=name):
                self.assertEqual(
                    self.client.get(reverse(f"club:{name}", kwargs=kwargs)).status_code,
                    200,
                )

    def test_anonymous_writes_require_login(self):
        original = (Paper.objects.count(), ReadingCard.objects.count(), Comment.objects.count())
        routes = [
            ("paper_create", {}, self.paper_data()),
            ("paper_update", {"pk": self.paper.pk}, self.paper_data()),
            ("paper_delete", {"pk": self.paper.pk}, {}),
            ("card_create", {"paper_pk": self.paper.pk}, self.card_data()),
            ("card_update", {"pk": self.card.pk}, self.card_data()),
            ("card_delete", {"pk": self.card.pk}, {}),
            ("comment_create", {"card_pk": self.card.pk}, {"content": "匿名评论"}),
            ("comment_update", {"pk": self.comment.pk}, {"content": "匿名编辑"}),
            ("comment_delete", {"pk": self.comment.pk}, {}),
            ("progress_update", {"paper_pk": self.paper.pk}, {"status": "read"}),
        ]
        for name, kwargs, data in routes:
            with self.subTest(route=name):
                response = self.client.post(reverse(f"club:{name}", kwargs=kwargs), data)
                self.assertEqual(response.status_code, 302)
        self.assertEqual(
            (Paper.objects.count(), ReadingCard.objects.count(), Comment.objects.count()), original
        )
        self.assertEqual(ReadingProgress.objects.count(), 0)

    def test_registration_creates_user_and_starts_session(self):
        response = self.client.post(
            reverse("club:register"),
            {"username": "newreader", "password1": "Paper-Reader!905", "password2": "Paper-Reader!905"},
        )
        self.assertEqual(response.status_code, 302)
        reader = User.objects.get(username="newreader")
        self.assertEqual(int(self.client.session["_auth_user_id"]), reader.pk)
        self.assertTrue(reader.check_password("Paper-Reader!905"))

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("club:register"),
            {"username": "newreader", "password1": "123", "password2": "123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newreader").exists())

    def test_login_and_logout_work_with_post(self):
        login_url = reverse("club:login")
        response = self.client.post(login_url, {"username": "alice", "password": "incorrect"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(login_url, {"username": "alice", "password": "Research-Club!42"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.alice.pk)
        logout_url = reverse("club:logout")
        self.assertEqual(self.client.get(logout_url).status_code, 405)
        self.assertEqual(self.client.post(logout_url).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_write_endpoints_require_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.alice)
        response = csrf_client.post(reverse("club:paper_create"), self.paper_data())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Paper.objects.count(), 1)

    def test_reader_can_create_paper_with_own_identity(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("club:paper_create"),
            self.paper_data(created_by=self.alice.pk),
        )
        self.assertEqual(response.status_code, 302)
        paper = Paper.objects.get(title="一篇新的共读论文")
        self.assertEqual(paper.created_by, self.bob)
        self.assertEqual(paper.year, 2024)

    def test_invalid_year_and_url_are_rejected(self):
        self.client.force_login(self.alice)
        for changes in ({"year": 0}, {"year": date.today().year + 100}, {"paper_url": "not-a-url"}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("club:paper_create"), self.paper_data(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Paper.objects.count(), 1)

    def test_paper_tags_and_doi_are_normalized(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("club:paper_create"),
            self.paper_data(tags=" 机器学习，AI;机器学习；复现 ", doi="https://doi.org/10.1234/test.2024"),
        )
        self.assertEqual(response.status_code, 302)
        paper = Paper.objects.get(title="一篇新的共读论文")
        self.assertEqual(paper.tag_list, ["机器学习", "AI", "复现"])
        self.assertEqual(paper.doi, "10.1234/test.2024")

    def test_owner_can_edit_paper(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("club:paper_update", args=[self.paper.pk]), self.paper_data(title="已更新的论文")
        )
        self.assertEqual(response.status_code, 302)
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.title, "已更新的论文")
        self.assertEqual(self.paper.created_by, self.alice)

    def test_non_owner_cannot_edit_or_delete_paper(self):
        self.client.force_login(self.bob)
        for name in ("paper_update", "paper_delete"):
            with self.subTest(route=name):
                url = reverse(f"club:{name}", args=[self.paper.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, self.paper_data()).status_code, 403)
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.title, "Attention Is All You Need · 共读")

    def test_paper_with_reading_card_is_protected_from_deletion(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("club:paper_delete", args=[self.paper.pk]))
        self.assertIn(response.status_code, (200, 302))
        self.assertTrue(Paper.objects.filter(pk=self.paper.pk).exists())
        self.assertTrue(ReadingCard.objects.filter(pk=self.card.pk).exists())

    def test_unreferenced_paper_deletes_only_on_post(self):
        paper = Paper.objects.create(created_by=self.alice, **self.paper_data())
        self.client.force_login(self.alice)
        url = reverse("club:paper_delete", args=[paper.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Paper.objects.filter(pk=paper.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Paper.objects.filter(pk=paper.pk).exists())

    def test_two_users_can_each_have_a_card_for_same_paper(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("club:card_create", kwargs={"paper_pk": self.paper.pk}),
            self.card_data(author=self.alice.pk),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReadingCard.objects.filter(paper=self.paper).count(), 2)
        card = ReadingCard.objects.get(paper=self.paper, author=self.bob)
        self.assertEqual(card.research_question, "这个研究解决什么问题？")
        self.assertEqual(ReadingProgress.objects.get(user=self.bob, paper=self.paper).status, "reading")

    def test_duplicate_card_submission_does_not_overwrite_existing_card(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("club:card_create", kwargs={"paper_pk": self.paper.pk}),
            self.card_data(reflection="不应该覆盖原卡片"),
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(ReadingCard.objects.filter(paper=self.paper, author=self.alice).count(), 1)
        self.card.refresh_from_db()
        self.assertEqual(self.card.reflection, "先理解机制，再验证结论。")

    def test_card_requires_core_fields_but_discussion_can_be_blank(self):
        self.client.force_login(self.bob)
        url = reverse("club:card_create", kwargs={"paper_pk": self.paper.pk})
        response = self.client.post(url, self.card_data(method=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReadingCard.objects.filter(author=self.bob).exists())
        self.assertEqual(self.client.post(url, self.card_data(discussion="")).status_code, 302)
        self.assertTrue(ReadingCard.objects.filter(author=self.bob).exists())

    def test_owner_can_update_card_and_reading_status(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("club:card_update", args=[self.card.pk]),
            self.card_data(reflection="增加一次复现实验。", status="read"),
        )
        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.reflection, "增加一次复现实验。")
        self.assertEqual(ReadingProgress.objects.get(user=self.alice, paper=self.paper).status, "read")

    def test_non_owner_cannot_modify_card(self):
        self.client.force_login(self.bob)
        for name in ("card_update", "card_delete"):
            with self.subTest(route=name):
                url = reverse(f"club:{name}", args=[self.card.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, self.card_data()).status_code, 403)
        self.assertTrue(ReadingCard.objects.filter(pk=self.card.pk).exists())

    def test_card_delete_requires_confirmation_post(self):
        self.client.force_login(self.alice)
        url = reverse("club:card_delete", args=[self.card.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(ReadingCard.objects.filter(pk=self.card.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(ReadingCard.objects.filter(pk=self.card.pk).exists())
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_reading_progress_is_independent_for_each_user(self):
        url = reverse("club:progress_update", kwargs={"paper_pk": self.paper.pk})
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(url, {"status": "reading"}).status_code, 302)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(url, {"status": "read"}).status_code, 302)
        self.assertEqual(ReadingProgress.objects.get(user=self.alice, paper=self.paper).status, "reading")
        self.assertEqual(ReadingProgress.objects.get(user=self.bob, paper=self.paper).status, "read")

    def test_progress_rejects_invalid_choice_and_get_does_not_write(self):
        self.client.force_login(self.alice)
        url = reverse("club:progress_update", kwargs={"paper_pk": self.paper.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {"status": "not-a-status"})
        self.assertIn(response.status_code, (200, 302, 400))
        self.assertFalse(ReadingProgress.objects.filter(user=self.alice, paper=self.paper).exists())

    def test_comment_create_and_delete_are_post_only(self):
        self.client.force_login(self.bob)
        create_url = reverse("club:comment_create", kwargs={"card_pk": self.card.pk})
        delete_url = reverse("club:comment_delete", args=[self.comment.pk])
        self.assertEqual(self.client.get(create_url).status_code, 405)
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(create_url, {"content": "这是一条新的共读评论。", "author": self.alice.pk})
        self.assertEqual(response.status_code, 302)
        comment = Comment.objects.get(content="这是一条新的共读评论。")
        self.assertEqual(comment.author, self.bob)
        self.assertEqual(comment.card, self.card)
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_blank_comment_is_not_saved(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("club:comment_create", kwargs={"card_pk": self.card.pk}), {"content": "   "}
        )
        self.assertIn(response.status_code, (200, 302, 400))
        self.assertEqual(Comment.objects.count(), 1)

    def test_public_comment_text_is_html_escaped(self):
        self.comment.content = '<script>alert("unsafe")</script>'
        self.comment.save()
        response = self.client.get(reverse("club:card_detail", args=[self.card.pk]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, self.comment.content)

    def test_only_comment_author_can_edit_and_delete(self):
        update_url = reverse("club:comment_update", args=[self.comment.pk])
        delete_url = reverse("club:comment_delete", args=[self.comment.pk])
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.post(update_url, {"content": "他人篡改"}).status_code, 403)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(update_url, {"content": "增加数据划分说明。"}).status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "增加数据划分说明。")

    def test_search_matches_title_authors_and_tags(self):
        url = reverse("club:paper_list")
        for query in ("Attention", "Vaswani", "自然语言处理"):
            with self.subTest(query=query):
                response = self.client.get(url, {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["page_obj"].object_list), [self.paper])
        response = self.client.get(url, {"q": "不存在的关键字"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_tag_filter_uses_complete_tag_not_substring(self):
        selected = Paper.objects.create(created_by=self.alice, **self.paper_data(title="AI论文", tags="AI,语言"))
        Paper.objects.create(created_by=self.alice, **self.paper_data(title="AIML论文", tags="AIML,统计"))
        response = self.client.get(reverse("club:paper_list"), {"tag": "AI"})
        self.assertEqual(list(response.context["page_obj"].object_list), [selected])

    def test_search_pagination_preserves_query(self):
        for index in range(11):
            Paper.objects.create(
                created_by=self.alice, **self.paper_data(title=f"Paging Paper {index:02d}")
            )
        response = self.client.get(reverse("club:paper_list"), {"q": "Paging"})
        self.assertEqual(response.context["page_obj"].paginator.count, 11)
        self.assertEqual(len(response.context["page_obj"].object_list), 9)
        self.assertContains(response, "q=Paging")
        self.assertContains(response, "page=2")
        second = self.client.get(reverse("club:paper_list"), {"q": "Paging", "page": 2})
        self.assertEqual(len(second.context["page_obj"].object_list), 2)

    def test_lists_have_stable_newest_first_order_with_timestamp_ties(self):
        now = timezone.now()
        first = Paper.objects.create(created_by=self.alice, **self.paper_data(title="排序论文一"))
        second = Paper.objects.create(created_by=self.alice, **self.paper_data(title="排序论文二"))
        Paper.objects.filter(pk=self.paper.pk).update(created_at=now - timedelta(days=1))
        Paper.objects.filter(pk__in=[first.pk, second.pk]).update(created_at=now)
        response = self.client.get(reverse("club:paper_list"))
        self.assertEqual(
            [paper.pk for paper in response.context["page_obj"].object_list],
            [second.pk, first.pk, self.paper.pk],
        )
        values = {key: value for key, value in self.card_data().items() if key != "status"}
        first_card = ReadingCard.objects.create(paper=first, author=self.alice, **values)
        second_card = ReadingCard.objects.create(paper=second, author=self.alice, **values)
        ReadingCard.objects.filter(pk=self.card.pk).update(updated_at=now - timedelta(days=1))
        ReadingCard.objects.filter(pk__in=[first_card.pk, second_card.pk]).update(updated_at=now)
        self.client.force_login(self.alice)
        response = self.client.get(reverse("club:my_cards"))
        self.assertEqual(
            [card.pk for card in response.context["page_obj"].object_list],
            [second_card.pk, first_card.pk, self.card.pk],
        )

    def test_my_cards_only_shows_current_reader_and_filters_status(self):
        bob_card = ReadingCard.objects.create(
            paper=self.paper, author=self.bob,
            **{key: value for key, value in self.card_data().items() if key != "status"},
        )
        ReadingProgress.objects.create(paper=self.paper, user=self.bob, status="read")
        ReadingProgress.objects.create(paper=self.paper, user=self.alice, status="reading")
        self.client.force_login(self.bob)
        url = reverse("club:my_cards")
        response = self.client.get(url)
        self.assertEqual(list(response.context["page_obj"].object_list), [bob_card])
        self.assertEqual(self.client.get(url, {"status": "reading"}).context["page_obj"].paginator.count, 0)
        self.assertEqual(self.client.get(url, {"status": "read"}).context["page_obj"].paginator.count, 1)

    def test_missing_progress_is_treated_as_unread(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("club:my_cards"), {"status": "unread"})
        self.assertEqual(list(response.context["page_obj"].object_list), [self.card])
        self.assertEqual(response.context["page_obj"].object_list[0].user_status, "unread")

    def test_missing_objects_return_404(self):
        for name in ("paper_detail", "card_detail", "paper_bibtex", "card_markdown"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(f"club:{name}", args=[999999])).status_code, 404)
