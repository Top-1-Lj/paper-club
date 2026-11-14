"""Repeatable curated-paper import with field-wise protection of manual edits."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.core.validators import URLValidator
from django.db import transaction

from .forms import PaperForm
from .models import ImportedPaper, Paper, ReadingCard

AI_NOTICE = "基于论文原文整理，AI辅助生成，待人工复核"
PAPER_FIELDS = ("title", "authors", "year", "abstract", "tags", "paper_url", "doi", "code_url")
CARD_FIELDS = ("research_question", "method", "results", "limitations", "reflection", "discussion")
CURATOR_NAME = "paperclub_ai"
CURATOR_EMAIL = "paperclub-ai@curation.paper-club.invalid"
PRIORITIES = {"xr-multimodal": 30, "chop": 20, "pfl-coalitions": 10}


def normalized_doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I).casefold()


def normalized_url(value):
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), parts.query, ""))


def normalized_title(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def load_records(directory):
    paths = sorted(Path(directory).glob("*.json"))
    if not paths:
        raise CommandError(f"没有可导入的 JSON 文件：{directory}")
    records, keys = [], set()
    validator = URLValidator(schemes=["http", "https"])
    for path in paths:
        try:
            raw = path.read_bytes()
            record = json.loads(raw.decode("utf-8-sig"))
            key = record["key"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", key) or key in keys:
                raise ValueError("来源 key 不合法或重复")
            form = PaperForm({field: record["paper"].get(field, "") for field in PAPER_FIELDS})
            if not form.is_valid():
                raise ValueError(str(form.errors.as_text()))
            paper = {field: form.cleaned_data[field] for field in PAPER_FIELDS}
            card = {field: record["card"][field].strip() for field in CARD_FIELDS}
            if any(not card[field] for field in CARD_FIELDS[:-1]):
                raise ValueError("阅读卡片必填字段为空")
            for field, value in card.items():
                if len(value) > 20000:
                    raise ValueError(f"卡片字段 {field} 超过长度限制")
            provenance = record["provenance"]
            if provenance.get("reading_basis") != "全文" or not isinstance(provenance.get("pdf_pages"), int) or provenance["pdf_pages"] < 1:
                raise ValueError("缺少全文阅读依据或 PDF 页数")
            if not provenance.get("pdf_filename") or not provenance.get("publication"):
                raise ValueError("缺少原始文件名或出版信息")
            if not provenance.get("metadata_sources") or not provenance.get("evidence"):
                raise ValueError("缺少元数据来源或关键结论对照")
            for source in provenance["metadata_sources"]:
                validator(source["url"])
                if not source.get("label"):
                    raise ValueError("来源链接缺少名称")
            keys.add(key)
            records.append({"key": key, "paper": paper, "card": card, "provenance": provenance, "digest": hashlib.sha256(raw).hexdigest()})
        except (KeyError, TypeError, AttributeError, ValueError, UnicodeError, ValidationError) as exc:
            raise CommandError(f"内容文件 {path.name} 校验失败：{exc}") from exc
    return records


def find_existing(paper_data):
    """Prefer identifiers; never silently pick among ambiguous existing records."""
    papers = list(Paper.objects.all())
    doi = normalized_doi(paper_data["doi"])
    candidates = [p for p in papers if doi and normalized_doi(p.doi) == doi]
    if not candidates:
        url = normalized_url(paper_data["paper_url"])
        candidates = [p for p in papers if normalized_url(p.paper_url) == url]
    if not candidates:
        title = normalized_title(paper_data["title"])
        candidates = [p for p in papers if normalized_title(p.title) == title]
    if len(candidates) > 1:
        raise CommandError(f"论文存在多个匹配记录，未自动合并：{paper_data['title']}")
    if candidates and doi and candidates[0].doi and normalized_doi(candidates[0].doi) != doi:
        raise CommandError(f"相同链接或标题对应不同 DOI，需人工核对：{paper_data['title']}")
    return candidates[0] if candidates else None


def merge_unedited(instance, incoming, baseline):
    """Only update fields that are still equal to our previous imported value."""
    new_baseline, edited, changed = dict(baseline), [], []
    for field, value in incoming.items():
        current = getattr(instance, field)
        if field not in baseline or current != baseline[field]:
            if current != value:
                edited.append(field)
            continue
        new_baseline[field] = value
        if current != value:
            setattr(instance, field, value)
            changed.append(field)
    if changed:
        instance.full_clean()
        instance.save(update_fields=changed + ["updated_at"])
    return new_baseline, edited


@transaction.atomic
def import_records(records):
    User = get_user_model()
    curator = User.objects.filter(username=CURATOR_NAME).first()
    if curator and (curator.email != CURATOR_EMAIL or curator.is_staff or curator.is_superuser):
        raise CommandError("原文导读账号名称被其他账号占用，未写入数据。请先核对账号归属。")
    if curator is None:
        curator = User(username=CURATOR_NAME, first_name="AI辅助导读", email=CURATOR_EMAIL)
        curator.set_unusable_password()
        curator.save()
    result = []
    for record in records:
        key, paper_data, card_data = record["key"], record["paper"], record["card"]
        source = ImportedPaper.objects.select_related("paper", "card").filter(source_key=key).first()
        new_paper = new_card = False
        if source:
            paper = source.paper
            paper_snapshot, paper_edits = merge_unedited(paper, paper_data, source.paper_snapshot)
        else:
            paper = find_existing(paper_data)
            paper_edits = []
            if paper is None:
                paper = Paper(created_by=curator, **paper_data)
                paper.full_clean()
                paper.save()
                new_paper = True
            # An existing user's paper is reference-only: all metadata stays theirs.
            paper_snapshot = dict(paper_data) if new_paper else {}
        priority = PRIORITIES.get(key, 1)
        if paper.featured_priority != priority:
            Paper.objects.filter(pk=paper.pk).update(featured_priority=priority)
            paper.featured_priority = priority
        card = source.card if source and source.card_id else ReadingCard.objects.filter(paper=paper, author=curator).first()
        if card is None:
            card = ReadingCard(paper=paper, author=curator, is_demo=False, **card_data)
            card.full_clean()
            card.save()
            card_snapshot, card_edits, new_card = dict(card_data), [], True
        elif source and source.card_id:
            card_snapshot, card_edits = merge_unedited(card, card_data, source.card_snapshot)
        else:
            if ImportedPaper.objects.filter(card=card).exists():
                raise CommandError(f"多个内容文件匹配同一篇导读论文，请核对来源 key：{key}")
            card_snapshot, card_edits = {}, []
        source, _ = ImportedPaper.objects.update_or_create(source_key=key, defaults={
            "paper": paper, "card": card, "provenance": record["provenance"],
            "paper_snapshot": paper_snapshot, "card_snapshot": card_snapshot,
            "source_digest": record["digest"],
        })
        result.append({"key": key, "paper_id": paper.pk, "card_id": card.pk,
                       "paper_created": new_paper, "card_created": new_card,
                       "preserved_paper_fields": paper_edits, "preserved_card_fields": card_edits})
    return result
