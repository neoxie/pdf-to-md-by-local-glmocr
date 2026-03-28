# PDF to Markdown Converter

基于本地 Ollama + GLM-OCR 的 PDF 转 Markdown 工具。

## 功能

- 将 PDF 文件转换为结构化的 Markdown
- 本地处理，无需 API 调用费用
- 支持中英文文档识别
- 自动识别标题层级、列表等文档结构
- **批量处理** - 支持文件夹输入，自动处理所有 PDF
- **自动容错** - glmocr 失败时自动 fallback 到直接 Ollama API

## 系统要求

- Python 3.10+
- [Ollama](https://ollama.ai/)
- Poppler (PDF 处理)

### 安装依赖

**macOS:**
```bash
brew install poppler
```

**Ubuntu:**
```bash
sudo apt-get install poppler-utils
```

**Windows:**
```bash
conda install -c conda-forge poppler
# 或下载 https://github.com/oschwartz10612/poppler-windows/releases
```

## 快速开始

### 1. 安装 Ollama 并拉取模型

```bash
# 安装 Ollama: https://ollama.ai/
ollama pull glm-ocr
```

### 2. 初始化项目

```bash
uv sync
```

### 3. 运行转换

```bash
# 单个文件
uv run python pdf2md.py input.pdf

# 指定输出文件名
uv run python pdf2md.py input.pdf -o output.md

# 指定输出目录
uv run python pdf2md.py input.pdf -d ./output

# 批量处理文件夹
uv run python pdf2md.py input/ -d output/
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入的 PDF 文件或包含 PDF 的文件夹 | 必填 |
| `-o, --output` | 输出文件名（仅单文件模式有效） | `<pdf_name>.md` |
| `-d, --dir` | 输出目录 | `./output` |

## 项目结构

```
play-glm-orc/
├── pdf2md.py       # 主脚本
├── config.yaml     # GLM-OCR 配置
├── pyproject.toml  # 项目依赖
├── input/          # 输入目录
└── output/         # 输出目录
```

## 错误排查

| 错误 | 解决方案 |
|------|----------|
| `poppler not found` | 安装 poppler: `brew install poppler` |
| `GLM-OCR model not found` | 拉取模型: `ollama pull glm-ocr` |
| `Cannot connect to Ollama` | 启动服务: `ollama serve` |
| `GGML_ASSERT ... failed` | 自动 fallback 到 Ollama API，无需手动处理 |

## 参考

- [GLM-OCR](https://github.com/zai-org/GLM-OCR)
- [Ollama](https://ollama.ai/)
