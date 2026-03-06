# AI44PT 综合交付包（更新版）

## 打包信息
- Bundle: AI44PT_handoff_bundle_20260211_140637
- Generated at: 2026-02-11 14:07:18
- Purpose: 将当前仓库最新工作进度（代码、提示词、样本、文档）打包给其他 AI 做综合分析。

## 1. 交付目标
这个交付包用于让第三方 AI 快速理解并分析当前项目状态，重点覆盖：

- 可运行的核心代码（批处理 + HF Demo）
- 关键提示词与理论文本
- 小规模样本输入（PDF/TXT）
- 最新输出样例与进度文档
- 当前工作区变更快照（用于追踪本轮更新）

## 2. 当前项目核心思路
项目采用“两阶段流水线”实现 4PT 文本分析：

1. `raw`：读取元数据与文档，调用 LLM，保存原始 JSON。
2. `parse`：回放 JSON，做结构化解析与投票/一致性分析，导出结果表。
3. `full`：串联执行 `raw + parse`。

该结构支持“生成与解析解耦”，在 API 失败或中断后可直接重解析，提升稳定性与可复现性。

## 3. 目录结构

a. `codebase/`：完整代码
- `code/` 主批处理流水线
- `hf_demo/` 交互式 Web 版本
- `requirements.txt`、`pyproject.toml` 等运行入口文件

b. `prompts/`：提示词与理论依据
- `prompts.py`
- `TheCodingTask.md`
- `ExecutiveSummary.md`
- `MainBody.md`

c. `samples/`：样本输入与输出
- `pdfs/`：2 个示例 PDF
- `texts/`：2 个示例 MD + 1 个 TXT
- `outputs/latest_analysis_result.xlsx`：最新结果样例

d. `docs/`：背景与进度
- `PROJECT_README.md` / `CODE_README.md`
- `CODE_IMPLEMENTATION_ISSUES.md`
- bugfix 日志
- `WORKSPACE_STATUS_SNAPSHOT.txt`（本次打包时的 git 状态）
- `BASE_COMMIT.txt`（基线 commit）

## 4. 给其他 AI 的建议阅读顺序
1. 本 `README.md`
2. `docs/WORKSPACE_STATUS_SNAPSHOT.txt`
3. `docs/CODE_IMPLEMENTATION_ISSUES.md`
4. `codebase/code/pipeline_main.py` 与 `codebase/code/batch_analyzer.py`
5. `codebase/code/response_parser.py` 与 `codebase/code/voting.py`
6. `prompts/` 全部文件
7. `samples/` 样本文件

## 5. 快速运行（本地）
```bash
conda activate NLP
pip install -r codebase/requirements.txt
```

准备 `.env`：
```env
OPENAI_API_KEY=your_key_here
```

运行：
```bash
python codebase/code/pipeline_main.py --stage full
```

调试：
```bash
python codebase/code/pipeline_main.py --stage full --debug
```

## 6. 备注
- 本包不含真实 API 密钥。
- 本包是“最新工作快照”，用于分析当前进度而非替代完整历史仓库。
