import re
from urllib.parse import urlsplit

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Comment, Paper, ReadingCard, ReadingProgress


class PaperForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = ["title", "authors", "year", "abstract", "tags", "paper_url", "doi", "code_url"]
        widgets = {
            "abstract": forms.Textarea(attrs={"rows": 5}),
            "title": forms.TextInput(attrs={"placeholder": "例如：Attention Is All You Need"}),
            "tags": forms.TextInput(attrs={"placeholder": "自然语言处理,深度学习"}),
        }

    def clean_tags(self):
        raw = self.cleaned_data["tags"].replace("，", ",").replace("；", ",").replace(";", ",")
        tags = list(dict.fromkeys(t.strip() for t in raw.split(",") if t.strip()))
        if len(tags) > 10 or any(len(t) > 30 for t in tags):
            raise forms.ValidationError("最多 10 个标签，每个标签最多 30 字。")
        return ",".join(tags)

    def clean_doi(self):
        value = self.cleaned_data["doi"].strip()
        value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
        if value and not re.fullmatch(r"10\.\d{4,9}/\S+", value):
            raise forms.ValidationError("请输入有效 DOI，例如 10.1038/nature14539，或留空。")
        return value

    def clean(self):
        data = super().clean()
        for field in ("paper_url", "code_url"):
            value = data.get(field)
            if value and urlsplit(value).scheme.lower() not in {"http", "https"}:
                self.add_error(field, "链接需要使用 http 或 https。")
        return data


class CardForm(forms.ModelForm):
    status = forms.ChoiceField(label="我的阅读状态", choices=ReadingProgress.Status.choices, initial=ReadingProgress.Status.READING)

    class Meta:
        model = ReadingCard
        fields = ["research_question", "method", "results", "limitations", "reflection", "discussion"]
        widgets = {field: forms.Textarea(attrs={"rows": 4}) for field in fields}


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {"content": forms.Textarea(attrs={"rows": 3, "placeholder": "分享你的理解，或提出一个值得一起讨论的问题……"})}


class ProgressForm(forms.ModelForm):
    class Meta:
        model = ReadingProgress
        fields = ["status"]


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "password1", "password2"]
