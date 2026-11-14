"""Unicode exports: escape BibTeX values, keep raw notes readable in Markdown."""
import re


def bibtex_escape(value):
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, " " if c in "\r\n\t" else c) for c in str(value))


def paper_bibtex(paper):
    # Semicolons are the unambiguous author separator; existing BibTeX 'and' is retained.
    authors = " and ".join(a.strip() for a in re.split(r"[;；]", paper.authors) if a.strip())
    fields = [("title", paper.title), ("author", authors), ("year", str(paper.year)), ("url", paper.paper_url)]
    if paper.doi:
        fields.append(("doi", paper.doi))
    if paper.tags:
        fields.append(("keywords", paper.tags))
    source = paper.import_sources.first()
    if source and source.provenance.get("publication"):
        fields.append(("note", source.provenance["publication"]))
    lines = [f"@misc{{paper{paper.pk},"]
    lines += [f"  {name} = {{{bibtex_escape(value)}}}," for name, value in fields]
    lines.append("}")
    return "\n".join(lines) + "\n"


def card_markdown(card):
    title = card.paper.title.replace("\r", " ").replace("\n", " ")
    lines = [f"# {title}", "", f"作者：{card.author.username}", f"论文：{card.paper.paper_url}", f"更新时间：{card.updated_at.isoformat()}", ""]
    if card.is_demo:
        lines += ["> 演示内容：以下阅读笔记用于功能展示，请以论文原文为准。", ""]
    source = getattr(card, "curated_source", None)
    if source:
        from .curation import AI_NOTICE
        lines += [f"> {AI_NOTICE}", f"> 阅读依据：用户提供的 PDF 全文，共 {source.provenance['pdf_pages']} 页。PDF 页码从文件首页起计。", ""]
    for field in ("research_question", "method", "results", "limitations", "reflection", "discussion"):
        label = card._meta.get_field(field).verbose_name
        lines += [f"## {label}", "", getattr(card, field) or "（暂无）", ""]
    if source:
        info = source.provenance
        lines += ["## 来源与核对说明", "", f"正式发表：{info['publication']}",
                  f"原始文件：{info['pdf_filename']}", ""]
        for item in info["metadata_sources"]:
            lines += [f"- {item['label']}：{item['url']}"]
        lines += ["", "### 核对说明与待确认项", ""]
        lines += [f"- {note}" for note in info.get("verification_notes", [])]
        lines += ["", "### 关键结论对照", ""]
        for item in info["evidence"]:
            lines += [f"- {item['claim']}（{item['location']}）：{item['detail']}"]
        lines.append("")
    return "\n".join(lines)
