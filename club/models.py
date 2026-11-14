from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Paper(models.Model):
    # Seed identity stays stable even when the demo's editable metadata changes.
    demo_key = models.CharField(max_length=80, unique=True, null=True, blank=True, editable=False)
    featured_priority = models.PositiveSmallIntegerField("共读优先级", default=0, db_index=True)
    title = models.CharField("论文标题", max_length=300)
    authors = models.CharField("作者", max_length=500, help_text="多位作者可用英文分号分隔。")
    year = models.PositiveSmallIntegerField("发表年份", validators=[MinValueValidator(1900)])
    abstract = models.TextField("摘要", validators=[MaxLengthValidator(15000)])
    tags = models.CharField("标签", max_length=250, blank=True, help_text="用逗号分隔，例如：自然语言处理,深度学习")
    paper_url = models.URLField("论文链接", max_length=1000)
    doi = models.CharField("DOI", max_length=255, blank=True)
    code_url = models.URLField("代码链接", max_length=1000, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="papers", verbose_name="录入者")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "论文"
        verbose_name_plural = "论文"

    def clean(self):
        super().clean()
        if self.year is not None and self.year > date.today().year + 1:
            raise ValidationError({"year": "年份不能超过明年。"})

    @property
    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def get_absolute_url(self):
        return reverse("club:paper_detail", kwargs={"pk": self.pk})

    def __str__(self):
        return self.title


class ReadingCard(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.PROTECT, related_name="cards", verbose_name="论文")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cards", verbose_name="作者")
    research_question = models.TextField("研究问题", validators=[MaxLengthValidator(20000)])
    method = models.TextField("核心方法", validators=[MaxLengthValidator(20000)])
    results = models.TextField("主要结果", validators=[MaxLengthValidator(20000)])
    limitations = models.TextField("局限", validators=[MaxLengthValidator(20000)])
    reflection = models.TextField("个人理解", validators=[MaxLengthValidator(20000)])
    discussion = models.TextField("待讨论问题", blank=True, validators=[MaxLengthValidator(20000)])
    is_demo = models.BooleanField("演示内容", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["paper", "author"], name="one_card_per_reader_and_paper")]
        verbose_name = "阅读卡片"
        verbose_name_plural = "阅读卡片"

    def get_absolute_url(self):
        return reverse("club:card_detail", kwargs={"pk": self.pk})

    def __str__(self):
        return f"{self.author} · {self.paper.title}"


class ReadingProgress(models.Model):
    class Status(models.TextChoices):
        UNREAD = "unread", "未读"
        READING = "reading", "在读"
        READ = "read", "已读"

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="progresses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reading_progresses")
    status = models.CharField("阅读状态", max_length=10, choices=Status.choices, default=Status.UNREAD)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["paper", "user"], name="one_progress_per_reader_and_paper")]
        verbose_name = "阅读进度"
        verbose_name_plural = "阅读进度"


class Comment(models.Model):
    card = models.ForeignKey(ReadingCard, on_delete=models.CASCADE, related_name="comments", verbose_name="阅读卡片")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments", verbose_name="作者")
    content = models.TextField("评论内容", validators=[MaxLengthValidator(2000)])
    is_demo = models.BooleanField("演示内容", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "评论"
        verbose_name_plural = "评论"

    def get_absolute_url(self):
        return f"{self.card.get_absolute_url()}#comment-{self.pk}"

    def __str__(self):
        return f"{self.author}: {self.content[:40]}"


class ImportedPaper(models.Model):
    """Source provenance and merge baselines, independent of editable titles/URLs."""
    source_key = models.SlugField(max_length=80, unique=True)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="import_sources")
    card = models.OneToOneField(ReadingCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="curated_source")
    provenance = models.JSONField(default=dict)
    paper_snapshot = models.JSONField(default=dict)
    card_snapshot = models.JSONField(default=dict)
    source_digest = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_key"]
        verbose_name = "原文导读来源"
        verbose_name_plural = "原文导读来源"
