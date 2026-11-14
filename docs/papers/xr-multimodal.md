# 原文核对：Toward Multimodal Privacy in XR

基于论文原文整理，AI辅助生成，待人工复核。

## 来源与阅读范围

- 阅读核对的完整12页PDF：`Toward_Multimodal_Privacy_in_XR_Design_and_Evaluation_of_Composite_Privatization_Methods_for_Gaze_and_Body_Tracking_Data.pdf`。
- 下文“PDF第N页”从文件第一页计，依次对应期刊页4396–4407；已读取正文、参考文献和附录。
- 已渲染并视觉核对PDF第1页（出版信息）、第8页（表3/表4）、第9页（表5与作者明确限制）。原PDF和页面渲染图只用于本地核对，未作为项目源码资料发布。
- 应用可复建内容位于 [数据文件](../../data/papers/xr-multimodal.json)，不是原文全文的复制。

## 元数据

| 项目 | 核对结果 |
| --- | --- |
| 正式标题 | Toward Multimodal Privacy in XR: Design and Evaluation of Composite Privatization Methods for Gaze and Body Tracking Data |
| 作者 | Azim Ibragimov; Ethan Wilson; Kevin R. B. Butler; Eakta Jain |
| 期刊 | IEEE Transactions on Visualization and Computer Graphics |
| 正式卷期 | 32(5), 4396–4407, May 2026 |
| 在线发表 | 2026-03-30；PDF首页另列当前版本2026-05-12 |
| 应用录入年份 | 2026，依据正式出版信息 |
| 预印本年份 | 未确认，保留为空；首页的2025-09-12为收稿日期，不能当成预印本发布日 |
| DOI | [10.1109/TVCG.2026.3679093](https://doi.org/10.1109/TVCG.2026.3679093) |
| 官方代码 | [azimIbragimov/XR-Privacy-SDK](https://github.com/azimIbragimov/XR-Privacy-SDK)，PDF第9页§8明确给出 |

出版信息由所提供PDF首页和官方SDK仓库的引用信息相互核对。[作者项目页](https://www.azimibragimov.com/publications/toward-multimodal-privacy-in-xr-design-and-evaluation-of-composite-privati)与 [IEEE VR 2026官方论文列表](https://ieeevr.org/2026/program/papers/)（P1964）用于核对研究题名、作者和会议展示背景。DOI网页本次未能直接通过检索工具读取；未因此更改原文明确给出的DOI。作者项目列表中的占位出版信息不作为正式卷期依据。

应用摘要为原创中文概括，阅读卡片将论文论断、基于表格的核算与额外讨论分开标注。

## 结论与证据对照

| 内容 | 原文位置 | 应保留的条件或解释 |
| --- | --- | --- |
| 攻击者可选择最强模态路径 | PDF第3页§3.2；第8页表3/表4表注 | 眼动、身体、融合三种IR的最大值，才是表注定义的整体系统风险。 |
| OpenNEEDS样本 | PDF第4页§5.2–5.3 | 原始44人，筛选后38人；跨会话匹配、EKYT、Rank-1 IR。 |
| 休闲效用阈值 | PDF第4页§5.1；第7页§7 | 眼动角偏差≤2°，身体位置偏差≤21 cm，依据既有文献的量化代理阈值。 |
| Chimera样本与构造 | PDF第5–6页§6.2、算法1 | GazeBaseVR眼动与BeatLeader身体数据跨人配对形成407个合成身份，不是407人的真实同步多模态记录。 |
| Wilson样本 | PDF第6页§6.2 | 26人的真实同步眼动/身体记录，任务为有时间要求的烹饪交互。 |
| 竞技身体效用 | PDF第5页§6.1；第7页§7 | SimSaber模拟游戏分数，阈值至少保留原始Beat Saber分数的80%；竞技眼动配置采用Wilson等人的既有评估。 |
| OpenNEEDS配对结果 | PDF第8页表3 | 眼动Smoothing＋身体DMM-Smoothing：融合IR从80.3%降到26.3%；三元组为27.6/21.1/26.3。 |
| Chimera配对结果 | PDF第8页表4上半部分 | 眼动Smoothing＋身体DMM-Spatial：融合IR从84.8%降到26.1%；三元组为23.9/26.1/26.1。 |
| 真实Wilson配对结果 | PDF第8页表4下半部分 | 同类型配对融合IR从92.3%降至30.8%；三元组为26.9/30.8/30.8。 |
| SDK实机开销 | PDF第9页§8、表5 | Meta Quest Pro与Unity Microgames；作者/非作者操作的FPS分别37.61→37.45、38.45→37.93，时延19.01/18.71 ms，额外内存47.0/48.1 MB。 |
| 作者明确限制 | PDF第9页§9 | 只研究重识别与眼动/身体；效用未直接做用户研究；独立组合损失的假设、保护交互效应与用户长期适应需要后续验证。 |

各识别率单位均为百分比，指标越低表示该攻击在指定实验下成功率越低，不表示完全匿名，也不能直接推广到未测量的属性推断攻击。

## 特别容易误读的三点

1. **26.3%是融合IR，而非该配置的整体风险。** 表3给定强攻击者会选三条路径的最大值，因此该配置整体风险为 `max(27.6,21.1,26.3)=27.6%`。该运算是对原表的核算，不是新增实验；若以最大值排序，也不应断言最小融合IR对应唯一最优系统配置。
2. **26.1%对应Chimera，真实Wilson数据集为30.8%。** 摘要的“竞技场景”概括不应抹去表4中不同数据集的结果。
3. **满足代理效用阈值不等于已验证所有用户体验。** 作者在§9明确表示未开展直接用户研究，且模态保护的交互效应可能叠加，也可能受用户适应影响。

## 待人工复核与复现事项

- 尚未确认独立预印本版本及其首次发布时间，预印本年份未填写。
- PDF第5页§5.3描述4折、75%/25%参与者划分，第6页§6.3又列Chimera训练361、测试46个身份并称沿用相同协议；应用分别标明了这些原文信息，精确折分、训练数据处理与超参数应进一步结合代码核对。
- 本次确认了SDK仓库的存在、来源与本文对应关系，没有下载或运行Unity代码，未复现实验数字或SDK性能。
- 原文结论、数字与页码已核对；阅读卡片仍需研究者人工审阅后用于正式学术报告。
