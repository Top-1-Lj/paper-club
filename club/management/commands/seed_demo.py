"""Create a repeatable, non-destructive demonstration collection.

Paper metadata is linked to its original arXiv record. Summaries, reading cards,
and comments are short, independently written demonstration text, not quotations
or a substitute for reading the papers.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from club.models import Comment, Paper, ReadingCard, ReadingProgress


DEMO_PASSWORD = "PaperClub2026!"
DEMO_ACCOUNTS = (
    ("lin", "林同学", "lin@demo.paper-club.invalid"),
    ("chen", "陈同学", "chen@demo.paper-club.invalid"),
)

# Years are the first arXiv submission year, not the later conference year.
# Full metadata and source links were checked against the original arXiv pages.
PAPERS = (
    {
        "title": "Attention Is All You Need",
        "authors": "Ashish Vaswani and Noam Shazeer and Niki Parmar and Jakob Uszkoreit and Llion Jones and Aidan N. Gomez and Lukasz Kaiser and Illia Polosukhin",
        "year": 2017,
        "arxiv": "1706.03762",
        "tags": "自然语言处理,Transformer,经典论文",
        "abstract": "【演示导读】研究仅使用注意力机制的序列建模架构，并在机器翻译任务中检验效果。完整论证和实验请阅读原文。",
        "question": "序列建模能否减少对循环结构的依赖，并更充分地并行计算？",
        "method": "梳理编码器、解码器、多头注意力与位置编码之间的关系，绘制一次前向传播的流程。",
        "result": "重点阅读机器翻译实验及消融分析，逐项核对训练设置；此处不填未经复核的实验数字。",
        "limitation": "继续查阅长序列计算成本、训练数据和评测任务对结论适用范围的影响。",
        "discussion": "位置编码与注意力分别提供了哪些信息？去掉其中一项会怎样？",
    },
    {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "authors": "Jacob Devlin and Ming-Wei Chang and Kenton Lee and Kristina Toutanova",
        "year": 2018,
        "arxiv": "1810.04805",
        "tags": "自然语言处理,预训练,Transformer",
        "abstract": "【演示导读】通过双向上下文预训练学习语言表示，再针对下游任务微调。演示条目使用首次预印本年份。",
        "question": "怎样利用双向上下文预训练，为不同语言理解任务提供通用表示？",
        "method": "对照预训练目标、输入表示与下游微调方式，整理每种任务实际使用的输出。",
        "result": "查阅论文中的语言理解和问答任务结果，比较预训练、模型规模与数据设置。",
        "limitation": "留意预训练目标与下游输入之间的差异，以及计算资源和语料覆盖范围。",
        "discussion": "双向上下文与自回归建模在训练目标上有什么差别？",
    },
    {
        "title": "Deep Residual Learning for Image Recognition",
        "authors": "Kaiming He and Xiangyu Zhang and Shaoqing Ren and Jian Sun",
        "year": 2015,
        "arxiv": "1512.03385",
        "tags": "计算机视觉,残差网络,经典论文",
        "abstract": "【演示导读】使用残差学习研究深层视觉网络的优化问题，包含图像分类及迁移实验。首次预印本发表于 2015 年。",
        "question": "增加网络深度时出现的优化困难，可以怎样通过网络结构缓解？",
        "method": "将普通映射与残差映射画成计算图，分别检查恒等捷径与投影捷径的用途。",
        "result": "对照普通网络和残差网络的训练表现，区分优化问题与泛化问题。",
        "limitation": "保持训练配方一致再做结构比较，不能把全部增益都归因于单一因素。",
        "discussion": "残差连接和简单增加网络宽度解决的是同一个问题吗？",
    },
    {
        "title": "Densely Connected Convolutional Networks",
        "authors": "Gao Huang and Zhuang Liu and Laurens van der Maaten and Kilian Q. Weinberger",
        "year": 2016,
        "arxiv": "1608.06993",
        "tags": "计算机视觉,特征复用,卷积网络",
        "abstract": "【演示导读】通过密集连接在多个层之间传递和复用特征，并研究视觉识别表现与参数效率。",
        "question": "不同层之间更充分地共享特征，能否改善信息流与参数利用？",
        "method": "画出一个小型 dense block，跟踪各层输入通道数量和特征拼接方式。",
        "result": "比较参数量、识别结果和连接方式，注意实验中的网络规模设置。",
        "limitation": "参数量较少不等于运行时显存和耗时必然更低，需要结合具体实现测量。",
        "discussion": "特征拼接与残差相加分别保留了哪些信息？",
    },
    {
        "title": "Auto-Encoding Variational Bayes",
        "authors": "Diederik P. Kingma and Max Welling",
        "year": 2013,
        "arxiv": "1312.6114",
        "tags": "生成模型,变分推断,概率建模",
        "abstract": "【演示导读】研究连续潜变量模型的变分推断，并通过重参数化构造可优化的学习方法。",
        "question": "潜变量后验难以直接计算时，怎样构造可以高效优化的近似推断过程？",
        "method": "逐步推导证据下界，并说明重参数化如何连接采样与梯度计算。",
        "result": "把理论推导与论文实验分别记录，检查生成结果和优化目标之间的关系。",
        "limitation": "近似分布的选择会影响表示能力；需要核对模型假设与具体数据的匹配情况。",
        "discussion": "重构项和正则项分别约束什么？改变权重后可能出现什么现象？",
    },
    {
        "title": "Generative Adversarial Networks",
        "authors": "Ian J. Goodfellow and Jean Pouget-Abadie and Mehdi Mirza and Bing Xu and David Warde-Farley and Sherjil Ozair and Aaron Courville and Yoshua Bengio",
        "year": 2014,
        "arxiv": "1406.2661",
        "tags": "生成模型,对抗学习,经典论文",
        "abstract": "【演示导读】通过生成器和判别器的对抗训练研究生成建模。标题采用当前 arXiv 条目的名称。",
        "question": "能否通过生成器与判别器之间的对抗过程学习数据分布？",
        "method": "分别列出两方的优化目标，再对照算法描述理解交替更新过程。",
        "result": "核对理论分析依赖的假设，和实际神经网络实验中的观察分开记录。",
        "limitation": "理论最优结论不直接保证实际训练稳定，需要观察优化过程和评价方式。",
        "discussion": "判别器过强时，生成器可能遇到什么训练困难？",
    },
    {
        "title": "Adam: A Method for Stochastic Optimization",
        "authors": "Diederik P. Kingma and Jimmy Ba",
        "year": 2014,
        "arxiv": "1412.6980",
        "tags": "优化算法,深度学习,经典论文",
        "abstract": "【演示导读】结合梯度矩估计与自适应步长研究随机优化。演示条目年份为首次预印本年份。",
        "question": "怎样根据梯度历史，自适应地调整不同参数的更新步长？",
        "method": "手算前两步的一阶矩、二阶矩及偏差修正，核对实现公式。",
        "result": "比较不同任务与超参数下的实验设置，避免把默认参数理解为普遍最优。",
        "limitation": "优化器效果依赖学习率、数据和任务；额外结论需要独立实验支持。",
        "discussion": "偏差修正为什么在训练初期尤其值得检查？",
    },
    {
        "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale",
        "authors": "Alexey Dosovitskiy and Lucas Beyer and Alexander Kolesnikov and Dirk Weissenborn and Xiaohua Zhai and Thomas Unterthiner and Mostafa Dehghani and Matthias Minderer and Georg Heigold and Sylvain Gelly and Jakob Uszkoreit and Neil Houlsby",
        "year": 2020,
        "arxiv": "2010.11929",
        "tags": "计算机视觉,Transformer,图像分类",
        "abstract": "【演示导读】将图像分块后送入 Transformer，研究大规模预训练及视觉任务迁移。",
        "question": "把图像变成图块序列后，Transformer 能否完成有效的视觉表示学习？",
        "method": "梳理图像分块、位置表示、分类标记以及预训练和微调流程。",
        "result": "把预训练数据规模和迁移任务一起记录，再比较模型表现。",
        "limitation": "需要同时考虑数据规模、计算预算及卷积结构提供的归纳偏置。",
        "discussion": "图块大小会怎样影响序列长度、局部信息和计算开销？",
    },
)


class Command(BaseCommand):
    help = "创建两位专属演示用户及论文共读样例；重复运行保留已有密码和内容。"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        # Validate *both* names before creating anything. Do not attach content
        # to a real account that happens to use a demonstration username.
        for username, _, email in DEMO_ACCOUNTS:
            existing = User.objects.filter(username=username).first()
            if existing and (
                existing.email != email or existing.is_staff or existing.is_superuser
            ):
                raise CommandError(
                    f"用户名 {username!r} 已被非演示账号占用，未写入演示数据。"
                    "请保留现有数据，在干净的开发数据库中初始化，"
                    "或先调整 seed_demo 的演示用户名。"
                )

        users = []
        created_counts = {"users": 0, "papers": 0, "cards": 0, "comments": 0}
        for username, display_name, email in DEMO_ACCOUNTS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": display_name, "email": email},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
                created_counts["users"] += 1
            users.append(user)

        for index, record in enumerate(PAPERS):
            demo_key = f"arxiv-{record['arxiv']}"
            source_url = f"https://arxiv.org/abs/{record['arxiv']}"
            # Upgrade collections produced before demo_key was introduced.
            # Only claim an original seed record owned by a validated demo
            # account. An ordinary reader's identical link stays untouched.
            if not Paper.objects.filter(demo_key=demo_key).exists():
                legacy_paper = (
                    Paper.objects.filter(
                        demo_key__isnull=True,
                        paper_url=source_url,
                        created_by__in=users,
                    )
                    .order_by("pk")
                    .first()
                )
                if legacy_paper is not None:
                    legacy_paper.demo_key = demo_key
                    legacy_paper.save(update_fields=["demo_key"])
            paper, created = Paper.objects.get_or_create(
                demo_key=demo_key,
                defaults={
                    "paper_url": source_url,
                    "title": record["title"],
                    "authors": record["authors"],
                    "year": record["year"],
                    "abstract": record["abstract"],
                    "tags": record["tags"],
                    "doi": f"10.48550/arXiv.{record['arxiv']}",
                    "code_url": "",
                    "created_by": users[index % 2],
                },
            )
            created_counts["papers"] += int(created)

            for user_index, author in enumerate(users):
                has_sample_card = index < 2 or index % 2 == user_index
                ReadingProgress.objects.get_or_create(
                    paper=paper,
                    user=author,
                    defaults={
                        "status": ("read" if index % 2 == 0 else "reading")
                        if has_sample_card
                        else "unread"
                    },
                )
                if not has_sample_card:
                    continue
                card, created = ReadingCard.objects.get_or_create(
                    paper=paper,
                    author=author,
                    defaults={
                        "research_question": "【演示阅读卡片】" + record["question"],
                        "method": record["method"],
                        "results": record["result"],
                        "limitations": record["limitation"],
                        "reflection": (
                            "【演示内容】这是一张用于展示共读流程的示例笔记，"
                            "不是经同行评审的结论。我的下一步是对照原文完成推导、"
                            "记录不理解之处，并补充独立复现实验。"
                            if user_index == 0
                            else "【演示内容】我会先复述论文解决的问题，再检查方法的关键假设。"
                            "本卡片展示与同学交换阅读视角的方式，具体结论请回到原文核对。"
                        ),
                        "discussion": record["discussion"],
                        "is_demo": True,
                    },
                )
                created_counts["cards"] += int(created)
                # Keep edited demonstration comments stable across reruns.
                _, created = Comment.objects.get_or_create(
                    card=card,
                    author=users[1 - user_index],
                    is_demo=True,
                    defaults={
                        "content": (
                            "【演示评论】这个问题适合放进下一次共读讨论。"
                            "建议先标记原文中的相关段落，再一起核对推导或实验设置。"
                        )
                    },
                )
                created_counts["comments"] += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                "演示数据准备完成。新增："
                f"{created_counts['users']} 个用户、{created_counts['papers']} 篇论文、"
                f"{created_counts['cards']} 张卡片、{created_counts['comments']} 条评论。"
            )
        )
        self.stdout.write(
            "演示账号 lin / chen；新建账号初始密码 PaperClub2026!。"
            "已有账号的密码和内容保持不变。"
        )
