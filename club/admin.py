from django.contrib import admin
from .models import Comment, ImportedPaper, Paper, ReadingCard, ReadingProgress


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ["title", "year", "created_by", "updated_at"]
    search_fields = ["title", "authors", "tags"]
    list_filter = ["year"]


@admin.register(ReadingCard)
class ReadingCardAdmin(admin.ModelAdmin):
    list_display = ["paper", "author", "is_demo", "updated_at"]
    search_fields = ["paper__title", "author__username"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["author", "card", "is_demo", "updated_at"]


@admin.register(ReadingProgress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "paper", "status"]
    list_filter = ["status"]


@admin.register(ImportedPaper)
class ImportedPaperAdmin(admin.ModelAdmin):
    list_display = ["source_key", "paper", "card", "updated_at"]
    readonly_fields = ["source_key", "paper", "card", "provenance", "paper_snapshot", "card_snapshot", "source_digest", "updated_at"]
