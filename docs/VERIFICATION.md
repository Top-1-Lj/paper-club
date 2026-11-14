# 测试指南

测试代码位于 [club/tests](../club/tests)。持续集成配置见 [tests.yml](../.github/workflows/tests.yml)，运行结果见 [GitHub Actions](https://github.com/Top-1-Lj/paper-club/actions/workflows/tests.yml)。

## 运行检查

在项目目录中执行：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

Linux / macOS 使用 `.venv/bin/python`。测试运行在独立数据库中，普通测试命令不会清空开发数据库。CI 在 Python 3.11 和 3.13 上运行相同检查。

## 自动化测试覆盖

| 范围 | 主要行为 |
| --- | --- |
| 账号与权限 | 匿名只读、作者编辑与删除、跨用户请求被拒绝 |
| 写入保护 | POST / CSRF 边界、评论 HTML 转义、表单校验 |
| 数据关系 | 同一读者对同一论文一张卡片、关联论文删除保护、个人进度独立 |
| 列表 | 标题、作者、标签检索，个人卡片筛选与稳定分页 |
| 导出 | 中文、特殊字符、可选 DOI、Markdown 来源信息 |
| 示例初始化 | 重复执行、已有密码与内容保留、同名账号冲突 |
| 导读导入 | 复用论文、保留人工修改、冲突回滚、优先排序、干净数据库重建 |

## 浏览器检查

启动应用后，按 [使用演示](DEMO.md) 体验核心流程，重点检查：

1. 两个独立会话分别登录不同账号，确认卡片编辑权限和阅读状态互不影响。
2. 写入并编辑论文、卡片与评论；提交无效年份、网址和空内容时，应显示错误而不保存。
3. 搜索存在和不存在的关键词，切换标签与页码，确认筛选条件保留且空状态可用。
4. 下载并打开 Markdown 和 BibTeX，检查中文、特殊字符、来源和缺失可选字段。
5. 重启服务后，确认保存的数据仍在同一数据库中。
6. 在桌面和手机宽度下检查长标题、链接、文件名、表单与来源说明。

## 数据导入检查

在独立开发数据库上依次重复执行 `seed_demo` 和 `import_papers`，确认没有重复记录；编辑导入内容后再次运行，确认人工修改被保留。相应回归测试见 [test_demo.py](../club/tests/test_demo.py) 和 [test_curation.py](../club/tests/test_curation.py)。

## 验证边界

应用测试验证的是软件行为与导入一致性。预置论文的实验结果来自对应原文；导读不等于对论文实验、模型或证明的独立复现。生产部署、并发负载和外部服务接入需要单独验证。
