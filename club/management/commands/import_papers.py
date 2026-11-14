from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from club.curation import import_records, load_records


class Command(BaseCommand):
    help = "从 data/papers 导入带原文依据的阅读卡片；保留已有用户内容和手动修改。"

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", type=Path, default=settings.BASE_DIR / "data" / "papers")

    def handle(self, *args, **options):
        records = load_records(options["data_dir"])
        try:
            results = import_records(records)
        except ValidationError as exc:
            raise CommandError(f"数据库内容校验失败，整次导入已回滚：{exc}") from exc
        for item in results:
            state = "新增论文" if item["paper_created"] else "复用论文"
            self.stdout.write(f"{item['key']}: {state} #{item['paper_id']}，阅读卡片 #{item['card_id']}")
            preserved = item["preserved_paper_fields"] + item["preserved_card_fields"]
            if preserved:
                self.stdout.write("  保留手动修改字段：" + ", ".join(preserved))
        self.stdout.write(self.style.SUCCESS(
            f"已处理 {len(results)} 篇，新增 {sum(r['paper_created'] for r in results)} 篇论文、"
            f"{sum(r['card_created'] for r in results)} 张卡片。原文 PDF 不会复制到仓库。"
        ))
