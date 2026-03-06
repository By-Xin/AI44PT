# AI44PT 综合交付包（用于第三方 AI 深度分析）

## 1. 这个包的目的
本交付包用于将当前仓库的核心进展浓缩为一个可直接投喂给其他 AI 的材料集，目标是让外部 AI 在不依赖完整历史仓库的前提下，快速理解并分析：

- 项目要解决的问题（4PT 框架下的政策文本分类）
- 当前可运行的主代码与 Web Demo 代码
- 关键提示词与理论文本来源
- 少量可直接试跑/审阅的样本文档
- 当前 bugfix 阶段的已知问题与修复日志

## 2. 工作目标与实现思路（简版）

### 2.1 项目工作目标
对政策/治理相关文本（主要是学术论文 PDF）执行结构化 4PT 分类分析，并将结果与人工编码对照，输出可审计、可复盘、可统计的分析报表。

### 2.2 主实现思路
采用“两阶段流水线 + 多次独立运行 + 多数投票”的方式：

1. `raw` 阶段：读取 Excel 元数据与 PDF，向 LLM 发起多次独立分析，保存原始 JSON 响应。
2. `parse` 阶段：从保存的原始 JSON 重建结构化答案，执行投票/一致性分析，生成 Excel 报告。
3. `full` 阶段：串联执行 `raw + parse`。

这种分阶段结构可实现“生成失败后重解析”，避免重复调用 API，提升鲁棒性与可追溯性。

## 3. 交付包目录结构

```text
AI44PT_handoff_bundle_20260211/
├── README.md                         # 本说明文件
├── codebase/                         # 可运行代码（核心）
│   ├── code/                         # 主批处理流水线代码
│   ├── hf_demo/                      # Hugging Face/Gradio 交互版代码
│   ├── main.py
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── requirements.txt.bak
├── prompts/                          # 提示词与理论指导文本
│   ├── prompts.py
│   ├── TheCodingTask.md
│   ├── ExecutiveSummary.md
│   └── MainBody.md
├── samples/                          # 少量样本（用于快速验证/分析）
│   ├── pdfs/
│   │   ├── sample_paper.pdf
│   │   └── jrg_59.pdf
│   └── texts/
│       ├── jrg_01.md
│       ├── jrg_14.md
│       └── jrgsamples_readme.txt
└── docs/                             # 项目背景与当前进展文档
    ├── PROJECT_README.md
    ├── CODE_README.md
    ├── AGENTS.md
    ├── CODE_IMPLEMENTATION_ISSUES.md
    ├── BUGFIX_IMPLEMENTATION_LOG_20260209.md
    └── BUGFIX_IMPLEMENTATION_LOG_20260210.md
```

## 4. 建议给其他 AI 的阅读顺序

1. `README.md`（本文件）：先建立整体认知。
2. `docs/CODE_IMPLEMENTATION_ISSUES.md`：把握当前 bugfix 重点。
3. `codebase/code/pipeline_main.py` + `codebase/code/batch_analyzer.py`：理解主流程。
4. `codebase/code/response_parser.py` + `codebase/code/voting.py`：理解解析与投票逻辑。
5. `prompts/` 下 4 个文件：理解提示词与判别依据。
6. `samples/`：结合样本做静态审查或小规模演练。

## 5. 快速运行（本地）

> 说明：本交付包不包含真实 API Key。

### 5.1 环境
```bash
conda activate NLP
pip install -r codebase/requirements.txt
```

### 5.2 配置
在运行目录准备 `.env`，至少包含：

```env
OPENAI_API_KEY=your_key_here
```

### 5.3 启动主流水线（在交付包根目录执行）
```bash
python codebase/code/pipeline_main.py --stage full
```

常用模式：
```bash
python codebase/code/pipeline_main.py --stage raw
python codebase/code/pipeline_main.py --stage parse --raw-path <raw_json_or_dir>
python codebase/code/pipeline_main.py --stage full --debug
```

## 6. 当前进度状态（截至打包时）
- 主体架构已模块化，可运行。
- 已进入 bugfix 与稳定性强化阶段。
- 关键问题与修复轨迹见 `docs/CODE_IMPLEMENTATION_ISSUES.md` 与两份 bugfix 日志。

## 7. 给第三方 AI 的建议分析任务
可要求第三方 AI 围绕以下方向输出评估报告：

1. 架构健壮性：两阶段流程、异常恢复、并发参数的风险点。
2. 解析可靠性：XML 标签解析、异常响应容错、字段对齐策略。
3. 一致性评估：多数投票与歧义分类是否存在系统偏差。
4. 提示词质量：是否存在可预见误判陷阱与优化空间。
5. 工程化改进：测试覆盖、日志可观测性、配置治理与可部署性。

## 8. 安全与边界说明
- 本包不包含 `.env` 与真实密钥。
- 样本文件仅提供少量用于分析演示，不代表全量数据分布。
- 如需全量复现实验，应回到原始仓库并使用完整数据目录。
