# 4PT分析系统 - 模块化版本

这是一个从Jupyter notebook风格重构为模块化架构的4PT框架分析系统。遵循奥卡姆剃刀原则，保持代码简洁而功能强大。

## 🏗️ 架构概览

系统采用清晰的模块化设计，每个模块负责特定的功能：

```
code/
├── config.py           # 配置管理
├── document_reader.py  # 文档读取器
├── analyzer.py         # 4PT分析核心
├── result_saver.py     # 结果输出处理
├── main.py            # 主系统类
├── 4pt_noRAG.py       # 向后兼容入口
└── __init__.py        # 包初始化
```

## 📦 模块说明

### 1. Config (`config.py`)
- 集中管理所有配置信息
- 文件路径、API密钥、模型设置
- 配置验证功能

### 2. DocumentReader (`document_reader.py`)
- 处理PDF和Markdown文件读取
- 支持按页面和按标题分节
- 统一的文档接口

### 3. FourPTAnalyzer (`analyzer.py`)
- 核心4PT框架分析逻辑
- OpenAI API调用处理
- 支持新旧API格式

### 4. ResultSaver (`result_saver.py`)
- 结果格式化和保存
- 支持TXT和Markdown格式输出
- 自动生成时间戳文件名

### 5. FourPTSystem (`main.py`)
- 主系统协调类
- 完整的分析流程管理
- 错误处理和用户交互

## 🚀 使用方法

### 基本使用
```bash
# 激活conda环境
conda activate NLP

# 运行分析
python code/4pt_noRAG.py
```

### 模块化使用
```python
from main import FourPTSystem

# 创建系统实例
system = FourPTSystem()

# 运行完整分析
system.run()
```

### 单独使用组件
```python
from analyzer import FourPTAnalyzer
from document_reader import DocumentReader

# 读取文档
reader = DocumentReader()
paper_pages = reader.read_pdf("path/to/paper.pdf")

# 执行分析
analyzer = FourPTAnalyzer()
result = analyzer.analyze_article(paper_pages, codebook_pages)
```

## 🎯 设计原则

1. **单一职责**: 每个模块专注于特定功能
2. **松耦合**: 模块间依赖最小化
3. **易扩展**: 新功能可以轻松添加
4. **向后兼容**: 保持原有接口可用
5. **奥卡姆剃刀**: 避免不必要的复杂性

## 📝 配置说明

系统使用`config.py`集中管理配置：

```python
class Config:
    # 项目路径
    PROJECT_ROOT = Path(__file__).parent.parent
    CODEBOOK_MD = PROJECT_ROOT / "data" / "processed" / "TheCodingTask.md"
    PAPER_PDF = PROJECT_ROOT / "data" / "processed" / "sample_paper.pdf"
    
    # OpenAI设置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLS_MODEL = "gpt-5-2025-08-07"
    
    # 输出设置
    RESULTS_DIR = PROJECT_ROOT / "results"
```

## 🔄 从Notebook的改进

1. **结构化**: 从线性notebook转为模块化架构
2. **可重用**: 组件可以独立使用和测试
3. **可维护**: 清晰的职责分离
4. **可扩展**: 新功能易于添加
5. **错误处理**: 更好的异常处理机制

## 📊 输出格式

系统支持两种输出格式：
- **TXT**: 纯文本格式，便于简单阅读
- **Markdown**: 格式化输出，包含元数据和结构化信息

输出文件自动包含：
- 分析结果
- 模型信息
- 时间戳
- 提示和响应长度统计

## 🛠️ 依赖项

主要依赖：
- `openai>=1.0.0` - OpenAI API客户端
- `pandas>=1.3.0` - 数据处理
- `PyMuPDF>=1.18.0` - PDF读取
- `python-dotenv>=0.19.0` - 环境变量管理

## 🎉 特性

- ✅ 模块化架构
- ✅ 配置集中管理
- ✅ 错误处理完善
- ✅ 向后兼容
- ✅ 多格式输出
- ✅ 自动文件管理
- ✅ 清晰的代码结构

---

*重构完成于2025年10月5日，遵循奥卡姆剃刀原则实现简洁而强大的模块化设计。*