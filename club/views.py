from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from . import exports
from .forms import CardForm, CommentForm, PaperForm, ProgressForm, RegisterForm
from .models import Comment, Paper, ReadingCard, ReadingProgress


def _owner(user, owner_id):
    if user.pk != owner_id:
        raise PermissionDenied("只有作者可以修改或删除这条内容。")


def _form_page(request, form, title, back_url, subtitle="", submit_label="保存"):
    return render(request, "club/form.html", {
        "form": form, "title": title, "subtitle": subtitle,
        "back_url": back_url, "submit_label": submit_label,
    })


def _add_status(objects, user, is_card=False):
    paper_ids = [o.paper_id if is_card else o.pk for o in objects]
    statuses = {}
    if user.is_authenticated:
        statuses = dict(ReadingProgress.objects.filter(user=user, paper_id__in=paper_ids).values_list("paper_id", "status"))
    labels = dict(ReadingProgress.Status.choices)
    for obj in objects:
        obj.user_status = statuses.get(obj.paper_id if is_card else obj.pk, "unread")
        obj.user_status_label = labels.get(obj.user_status, "未读")
    return statuses


@require_http_methods(["GET"])
def paper_list(request):
    q, tag = request.GET.get("q", "").strip(), request.GET.get("tag", "").strip()
    queryset = Paper.objects.select_related("created_by").annotate(card_count=Count("cards")).order_by("-featured_priority", "-created_at", "-pk")
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(authors__icontains=q) | Q(tags__icontains=q))
    if tag:
        queryset = queryset.filter(Q(tags__iexact=tag) | Q(tags__istartswith=tag + ",") | Q(tags__iendswith="," + tag) | Q(tags__icontains="," + tag + ","))
    page_obj = Paginator(queryset, 9).get_page(request.GET.get("page"))
    papers = list(page_obj.object_list)
    page_obj.object_list = papers
    progress_map = _add_status(papers, request.user)
    available_tags = sorted({tag for raw in Paper.objects.values_list("tags", flat=True) for tag in raw.split(",") if tag})
    return render(request, "club/paper_list.html", {
        "papers": papers, "page_obj": page_obj, "q": q, "tag": tag,
        "available_tags": available_tags, "progress_map": progress_map,
        "total_papers": Paper.objects.count(), "total_cards": ReadingCard.objects.count(),
        "total_members": get_user_model().objects.filter(is_active=True).count(),
        "recent_cards": ReadingCard.objects.select_related("paper", "author", "curated_source").annotate(comment_count=Count("comments")).order_by("-updated_at", "-pk")[:6],
        "featured_paper": Paper.objects.annotate(card_count=Count("cards")).order_by("-card_count", "-pk").first(),
    })


def paper_detail(request, pk):
    paper = get_object_or_404(Paper.objects.select_related("created_by"), pk=pk)
    cards = paper.cards.select_related("author", "curated_source").annotate(comment_count=Count("comments")).order_by("-updated_at", "-pk")
    progress = my_card = None
    if request.user.is_authenticated:
        progress = ReadingProgress.objects.filter(paper=paper, user=request.user).first()
        my_card = cards.filter(author=request.user).first()
    return render(request, "club/paper_detail.html", {
        "paper": paper, "cards": cards, "my_card": my_card, "progress": progress,
        "progress_form": ProgressForm(instance=progress), "status_choices": ReadingProgress.Status.choices,
        "source": paper.import_sources.select_related("card").first(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def paper_create(request):
    form = PaperForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        paper = form.save(commit=False)
        paper.created_by = request.user
        paper.save()
        messages.success(request, "论文已加入共读书架。")
        return redirect(paper)
    return _form_page(request, form, "添加论文", reverse("club:paper_list"), "把值得一起阅读的论文放进书架。", "添加到书架")


@login_required
@require_http_methods(["GET", "POST"])
def paper_update(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    _owner(request.user, paper.created_by_id)
    form = PaperForm(request.POST if request.method == "POST" else None, instance=paper)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "论文信息已更新。")
        return redirect(paper)
    return _form_page(request, form, "编辑论文", paper.get_absolute_url())


@login_required
@require_http_methods(["GET", "POST"])
def paper_delete(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    _owner(request.user, paper.created_by_id)
    protected = paper.cards.exists()
    if request.method == "POST":
        if not protected:
            try:
                paper.delete()
            except ProtectedError:
                protected = True
            else:
                messages.success(request, "论文已删除。")
                return redirect("club:paper_list")
        messages.error(request, "这篇论文已有阅读卡片，为保留共读内容，暂不能删除。")
        return redirect(paper)
    return render(request, "club/confirm_delete.html", {
        "object": paper, "title": "删除论文", "protected": protected,
        "back_url": paper.get_absolute_url(),
        "description": "论文已有阅读卡片，无法直接删除。" if protected else "删除论文后，其个人阅读状态也会一并删除。",
    })


def card_detail(request, pk):
    card = get_object_or_404(ReadingCard.objects.select_related("paper", "author", "curated_source"), pk=pk)
    progress = None
    if request.user.is_authenticated:
        progress = ReadingProgress.objects.filter(paper=card.paper, user=request.user).first()
    return render(request, "club/card_detail.html", {
        "card": card, "comments": card.comments.select_related("author"),
        "comment_form": CommentForm(), "progress": progress,
        "source": getattr(card, "curated_source", None),
    })


@login_required
@require_http_methods(["GET", "POST"])
def card_create(request, paper_pk):
    paper = get_object_or_404(Paper, pk=paper_pk)
    existing = ReadingCard.objects.filter(paper=paper, author=request.user).first()
    if existing:
        messages.info(request, "你已经为这篇论文写过卡片，可以继续编辑。")
        return redirect("club:card_update", pk=existing.pk)
    progress = ReadingProgress.objects.filter(paper=paper, user=request.user).first()
    form = CardForm(request.POST if request.method == "POST" else None, initial={"status": progress.status if progress else "reading"})
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                card = form.save(commit=False)
                card.paper, card.author = paper, request.user
                card.save()
                ReadingProgress.objects.update_or_create(paper=paper, user=request.user, defaults={"status": form.cleaned_data["status"]})
        except IntegrityError:
            existing = ReadingCard.objects.filter(paper=paper, author=request.user).first()
            if not existing:
                raise
            return redirect(existing)
        messages.success(request, "阅读卡片已发布，邀请同学一起讨论吧。")
        return redirect(card)
    return _form_page(request, form, "撰写阅读卡片", paper.get_absolute_url(), paper.title, "发布阅读卡片")


@login_required
@require_http_methods(["GET", "POST"])
def card_update(request, pk):
    card = get_object_or_404(ReadingCard.objects.select_related("paper"), pk=pk)
    _owner(request.user, card.author_id)
    progress = ReadingProgress.objects.filter(paper=card.paper, user=request.user).first()
    form = CardForm(request.POST if request.method == "POST" else None, instance=card, initial={"status": progress.status if progress else "unread"})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            ReadingProgress.objects.update_or_create(paper=card.paper, user=request.user, defaults={"status": form.cleaned_data["status"]})
        messages.success(request, "卡片与阅读状态已保存。")
        return redirect(card)
    return _form_page(request, form, "编辑阅读卡片", card.get_absolute_url(), card.paper.title)


@login_required
@require_http_methods(["GET", "POST"])
def card_delete(request, pk):
    card = get_object_or_404(ReadingCard.objects.select_related("paper"), pk=pk)
    _owner(request.user, card.author_id)
    if request.method == "POST":
        paper = card.paper
        card.delete()
        messages.success(request, "阅读卡片及其评论已删除。")
        return redirect(paper)
    return render(request, "club/confirm_delete.html", {
        "object": card, "title": "删除阅读卡片", "back_url": card.get_absolute_url(),
        "description": "这张卡片下的全部评论也会删除，个人阅读状态会保留。",
    })


@login_required
@require_POST
def comment_create(request, card_pk):
    card = get_object_or_404(ReadingCard, pk=card_pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.card, comment.author = card, request.user
        comment.save()
        messages.success(request, "评论已发布。")
        return redirect(comment.get_absolute_url())
    return render(request, "club/card_detail.html", {
        "card": card, "comments": card.comments.select_related("author"), "comment_form": form,
        "source": getattr(card, "curated_source", None),
    }, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def comment_update(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("card"), pk=pk)
    _owner(request.user, comment.author_id)
    form = CommentForm(request.POST if request.method == "POST" else None, instance=comment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "评论已更新。")
        return redirect(comment.get_absolute_url())
    return _form_page(request, form, "编辑评论", comment.get_absolute_url())


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment.objects.select_related("card"), pk=pk)
    _owner(request.user, comment.author_id)
    url = comment.card.get_absolute_url()
    comment.delete()
    messages.success(request, "评论已删除。")
    return redirect(url)


@login_required
@require_POST
def progress_update(request, paper_pk):
    paper = get_object_or_404(Paper, pk=paper_pk)
    form = ProgressForm(request.POST)
    if form.is_valid():
        ReadingProgress.objects.update_or_create(user=request.user, paper=paper, defaults={"status": form.cleaned_data["status"]})
        messages.success(request, "你的阅读状态已更新。")
    else:
        messages.error(request, "请选择有效的阅读状态。")
    return redirect(paper)


@login_required
def my_cards(request):
    q, status = request.GET.get("q", "").strip(), request.GET.get("status", "").strip()
    cards = ReadingCard.objects.filter(author=request.user).select_related("paper", "author").annotate(comment_count=Count("comments")).order_by("-updated_at", "-pk")
    if q:
        cards = cards.filter(Q(paper__title__icontains=q) | Q(paper__authors__icontains=q) | Q(paper__tags__icontains=q) | Q(reflection__icontains=q))
    if status in dict(ReadingProgress.Status.choices):
        ids = ReadingProgress.objects.filter(user=request.user, status=status).values_list("paper_id", flat=True)
        if status == "unread":
            any_progress = ReadingProgress.objects.filter(user=request.user).values_list("paper_id", flat=True)
            cards = cards.filter(Q(paper_id__in=ids) | ~Q(paper_id__in=any_progress))
        else:
            cards = cards.filter(paper_id__in=ids)
    else:
        status = ""
    page_obj = Paginator(cards, 9).get_page(request.GET.get("page"))
    objects = list(page_obj.object_list)
    page_obj.object_list = objects
    _add_status(objects, request.user, is_card=True)
    return render(request, "club/my_cards.html", {
        "cards": objects, "page_obj": page_obj, "q": q, "status": status,
        "status_choices": ReadingProgress.Status.choices,
        "total_cards": ReadingCard.objects.filter(author=request.user).count(),
    })


def paper_bibtex_export(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    response = HttpResponse(exports.paper_bibtex(paper), content_type="application/x-bibtex; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="paper-{paper.pk}.bib"'
    return response


def card_markdown_export(request, pk):
    card = get_object_or_404(ReadingCard.objects.select_related("paper", "author"), pk=pk)
    response = HttpResponse(exports.card_markdown(card), content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="card-{card.pk}.md"'
    return response


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("club:paper_list")
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "欢迎来到纸间，开始你的第一场共读吧。")
        return redirect("club:paper_list")
    return render(request, "registration/register.html", {"form": form})
