# 导读数据与来源

预置导读包含论文元数据、六个结构化笔记字段及来源定位。内容标注为 **“基于论文原文整理，AI辅助生成，待人工复核”**，区分原文结论、表格转录和辅助理解。PDF 页码从对应文件首页起计。

## 数据集

| 来源标识 | 论文 | 正式出版 | 来源对照 |
| --- | --- | --- | --- |
| `xr-multimodal` | Toward Multimodal Privacy in XR | IEEE TVCG 32(5):4396–4407, 2026 | [核对说明](papers/xr-multimodal.md) |
| `chop` | CHOP: Breaking Anonymity in XR | IEEE VR 2026, pp.626–636 | [核对说明](papers/chop.md) |
| `pfl-coalitions` | Toward Personalized Federated Learning via Overlapping Coalition Formation Game | IEEE TMC 25(8):11790–11803, 2026 | [核对说明](papers/pfl-coalitions.md) |

正式发表年份与预印本年份分别记录；未核实的预印本年为 `null`。代码链接只有在来源明确时填写。多模态隐私论文包含已核对的官方 SDK 地址；CHOP 与个性化联邦学习论文的代码地址保持空值。

核对说明保留了需要进一步确认的内容，包括多模态实验的风险指标与划分口径、CHOP 表格和正文的数字差异，以及个性化联邦学习论文的作者记录差异与附录缺失情况。

## 文件结构

每篇导读对应一个 JSON 文件：

- [xr-multimodal.json](../data/papers/xr-multimodal.json)
- [chop.json](../data/papers/chop.json)
- [pfl-coalitions.json](../data/papers/pfl-coalitions.json)

| 字段 | 内容 |
| --- | --- |
| `key` | 固定来源标识，用于重复导入时保持关联 |
| `paper` | 标题、作者、年份、摘要、标签、DOI、原文与代码链接 |
| `card` | 研究问题、核心方法、结果、局限、个人理解、讨论问题 |
| `provenance` | 出版信息、版本信息、元数据来源、证据位置和待核实项 |

论文正文不随数据集分发，来源链接保留在元数据中。核对版本的文件名与页数用于定位证据；导入运行无需读取原 PDF。

## 导入

完成依赖安装和数据库迁移后执行：

```powershell
.\.venv\Scripts\python.exe manage.py import_papers
```

Linux / macOS 使用 `.venv/bin/python`。需要基础样例账号和评论时，可另行执行 `seed_demo`。

导入其他相同结构的数据目录：

```powershell
.\.venv\Scripts\python.exe manage.py import_papers --data-dir path/to/papers
```

命令输出实际创建或复用的论文和卡片编号。页面主键由数据库生成，使用时以命令输出及页面链接为准。

## 重复导入与冲突处理

导入先校验整批文件，再在事务内写入。首次依次按 DOI、原文链接、规范化标题寻找已有论文；多个匹配项或 DOI 冲突会中止自动合并并回滚。

复用已有论文时，保留其元数据、录入者、卡片和评论，并为导读建立独立卡片。新建的导入内容保存固定来源标识和上一版字段值；后续仅更新仍等于上一版导入值的字段，手动修改的字段保持原样。修改标题或链接不会破坏来源关联。

导读账号 `paperclub_ai` 显示为“AI辅助导读”，不开放密码登录。读者用个人账号维护自己的卡片和评论。导入不会替其他读者修改阅读状态。

三篇预置论文按共读优先级排列在普通论文之前，仍可通过常规检索和标签筛选访问。

## 扩充导读

准备符合上述结构的 JSON 文件，为关键结论补充可核查的原文位置，明确实验条件、指标和未确认信息。讨论问题与额外推断应标为辅助理解。

导入与合并行为的测试见 [test_curation.py](../club/tests/test_curation.py)；测试方法见 [测试指南](VERIFICATION.md)。
