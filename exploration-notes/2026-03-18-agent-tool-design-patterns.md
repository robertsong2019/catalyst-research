# 🛠️ AI Agent 工具设计模式 - 深度探索笔记

**日期**: 2026-03-18 20:00 - 21:30 (Asia/Shanghai)
**探索时长**: 1.5 小时
**主题**: Agent 工具设计模式 - 如何为 AI Agent 设计高效、可组合、安全的工具
**动机来源**:
- Lilian Weng 的 Agent 框架: Tool use 是 Agent 三大支柱之一
- LangChain Harness 研究: Bash + 代码执行 = 通用工具
- gstack: 10 个专业化定制工具的成功实践
- OpenClaw 技能系统: AgentSkills 规范的实现

---

## 📚 核心理论：为什么工具设计至关重要？

### 1. Agent 能力的边界

**原始模型的局限性**:
- 只有权重和当前上下文
- 无法访问外部信息（当前时间、实时数据、文件系统）
- 无法执行实际操作（发送消息、调用 API、修改文件）

**工具 = 能力扩展**:
```
Model + Tools = Agent
模型（智能） + 工具（能力） = 智能体
```

**LangChain 的观点**:
> Harness 是所有不是模型本身的代码、配置和执行逻辑。原始模型不是 Agent，但当 Harness 给它状态、工具执行、反馈循环和可执行约束时，它就变成了 Agent。

### 2. 工具设计的三层抽象

```
┌─────────────────────────────────────┐
│  Layer 3: Orchestration             │
│  工具编排（多工具协作）               │
│  - 工具链（Tool Chains）             │
│  - 工具选择策略                      │
│  - 错误处理与回退                    │
└──────────────┬──────────────────────┘
               │
┌──────────────┴──────────────────────┐
│  Layer 2: Interface                  │
│  工具接口（Agent 与工具的交互）       │
│  - 参数验证                          │
│  - 结果解析                          │
│  - 错误处理                          │
└──────────────┬──────────────────────┘
               │
┌──────────────┴──────────────────────┐
│  Layer 1: Implementation             │
│  工具实现（底层功能）                 │
│  - 核心逻辑                          │
│  - 外部 API 调用                     │
│  - 文件系统操作                      │
└─────────────────────────────────────┘
```

---

## 📖 AgentSkills 规范深度解析

### 1. 规范概述

**AgentSkills** 是一个开放的标准，定义了如何为 AI Agent 设计技能/工具。

**核心原则**:
1. **渐进式披露** (Progressive Disclosure): 只加载描述，完整指令按需加载
2. **相对路径引用**: 从技能目录引用脚本和资源
3. **前置元数据驱动**: 通过 YAML frontmatter 定义元数据
4. **安全性优先**: 技能可以指示模型执行任何操作，需要审查

### 2. 技能结构

```
my-skill/
├── SKILL.md              # 必需：前置元数据 + 指令
├── scripts/              # 辅助脚本
│   ├── process.sh
│   └── validate.py
├── references/           # 详细文档（按需加载）
│   ├── api-reference.md
│   └── examples.md
└── assets/               # 静态资源
    └── template.json
```

**设计理念**:
- **单一入口**: `SKILL.md` 是唯一的入口点
- **模块化**: 脚本、文档、资源分离
- **可扩展**: 可以添加任何需要的文件和目录

### 3. 前置元数据（Frontmatter）

```yaml
---
name: my-skill                    # 必需：技能名称（1-64字符）
description: What this skill does # 必需：描述（最大1024字符）
license: MIT                      # 可选：许可证
compatibility: Node.js 18+        # 可选：环境要求
metadata:                         # 可选：自定义元数据
  {
    "openclaw":
      {
        "emoji": "🛠️",
        "requires": { "bins": ["node"], "env": ["API_KEY"] },
        "always": false,
        "os": ["darwin", "linux"]
      }
  }
allowed-tools: read write exec    # 可选：预批准的工具
disable-model-invocation: false   # 可选：是否隐藏从系统提示
---
```

**关键字段解析**:

1. **name**: 
   - 规则：小写字母、数字、连字符
   - 必须匹配父目录名
   - 示例：`pdf-processing`, `data-analysis`

2. **description**:
   - **最重要的字段**！决定 Agent 何时加载此技能
   - 最佳实践：具体、明确、包含触发条件
   - 好的例子：`Extracts text and tables from PDF files. Use when working with PDF documents.`
   - 差的例子：`Helps with PDFs.`

3. **metadata.openclaw.requires**:
   - `bins`: 必须存在于 PATH 的二进制文件
   - `env`: 必须存在的环境变量
   - `config`: 必须为真的配置路径
   - `anyBins`: 至少一个必须存在

4. **metadata.openclaw.install**:
   - 定义如何安装依赖
   - 支持：brew, node, go, uv, download
   - 示例：
     ```json
     {
       "id": "brew",
       "kind": "brew",
       "formula": "ripgrep",
       "bins": ["rg"],
       "label": "Install ripgrep (brew)"
     }
     ```

### 4. 渐进式披露机制

**加载流程**:
```
1. 扫描技能目录
   ↓
2. 提取 name + description
   ↓
3. 将描述加入系统提示（XML 格式）
   ↓
4. 当任务匹配时，Agent 使用 read 工具加载完整 SKILL.md
   ↓
5. Agent 遵循指令，使用相对路径引用脚本和资源
```

**为什么重要**:
- **节省 token**: 不需要在每次对话中都加载完整指令
- **按需加载**: 只在需要时才加载详细信息
- **性能优化**: 减少上下文窗口占用

---

## 🏗️ OpenClaw 技能系统架构

### 1. 加载位置与优先级

```
优先级（从高到低）:
1. <workspace>/skills          # 工作区技能（项目特定）
2. ~/.openclaw/skills          # 托管/本地技能（用户级别）
3. Bundled skills              # 内置技能（随安装包提供）
4. skills.load.extraDirs      # 额外配置的目录
```

**设计理由**:
- **项目隔离**: 不同项目可以有不同版本的技能
- **用户定制**: 用户可以覆盖内置技能
- **共享技能**: 通过 extraDirs 实现多 Agent 共享

### 2. 多 Agent 场景

```
Agent 1 (工作区: ~/project-a)
  ├── <workspace>/skills       # 仅 Agent 1 可见
  ├── ~/.openclaw/skills       # 所有 Agent 共享
  └── Bundled skills           # 所有 Agent 共享

Agent 2 (工作区: ~/project-b)
  ├── <workspace>/skills       # 仅 Agent 2 可见
  ├── ~/.openclaw/skills       # 所有 Agent 共享
  └── Bundled skills           # 所有 Agent 共享
```

**最佳实践**:
- **项目特定技能**: 放在 `<workspace>/skills`
- **通用技能**: 放在 `~/.openclaw/skills`
- **团队共享**: 使用 Git 仓库 + `skills.load.extraDirs`

### 3. 门控机制（Gating）

**加载时过滤**:
```yaml
metadata:
  {
    "openclaw":
      {
        "requires": {
          "bins": ["uv"],           # 需要 uv 在 PATH 中
          "env": ["API_KEY"],       # 需要环境变量
          "config": ["browser.enabled"]  # 需要配置项为真
        },
        "os": ["darwin", "linux"],  # 仅在这些操作系统上加载
        "always": false             # 是否总是加载（跳过其他门控）
      }
  }
```

**为什么需要门控**:
- **环境适配**: 不同环境有不同的工具可用
- **依赖管理**: 确保依赖存在才加载技能
- **安全性**: 避免在不可信环境中加载敏感技能

### 4. 配置覆盖

**~/.openclaw/openclaw.json**:
```json
{
  "skills": {
    "entries": {
      "nano-banana-pro": {
        "enabled": true,
        "apiKey": {
          "source": "env",
          "provider": "default",
          "id": "GEMINI_API_KEY"
        },
        "env": {
          "CUSTOM_VAR": "value"
        }
      }
    }
  }
}
```

**用途**:
- **启用/禁用**: 控制技能是否加载
- **注入密钥**: 安全地提供 API 密钥
- **环境变量**: 为技能提供配置

---

## 🎯 工具设计的核心模式

### 模式 1: 单一职责工具（Single Responsibility）

**定义**: 每个工具只做一件事，并做好它。

**示例**:
```yaml
---
name: pdf-extract-text
description: Extract text content from PDF files. Use when you need to read text from PDF documents.
---

# PDF Text Extraction

## Usage
\`\`\`bash
./scripts/extract-text.sh <pdf-file>
\`\`\`

## Output
Plain text content extracted from the PDF.
```

**优点**:
- ✅ 易于理解和测试
- ✅ 易于组合使用
- ✅ 错误定位清晰

**缺点**:
- ⚠️ 可能需要多个工具协作完成复杂任务

### 模式 2: 工具链（Tool Chain）

**定义**: 多个工具按顺序执行，前一个工具的输出是后一个工具的输入。

**示例流程**:
```
PDF 文件
  ↓
[pdf-extract-text] → 提取文本
  ↓
[text-summarize] → 生成摘要
  ↓
[text-translate] → 翻译摘要
  ↓
最终结果
```

**实现方式**:
1. **显式链**: Agent 手动调用多个工具
2. **隐式链**: 创建一个包装工具，内部调用其他工具

**包装工具示例**:
```yaml
---
name: pdf-pipeline
description: Complete PDF processing pipeline: extract text, summarize, and translate. Use for end-to-end PDF processing.
---

# PDF Processing Pipeline

## Usage
\`\`\`bash
./scripts/pipeline.sh <pdf-file> --summarize --translate <language>
\`\`\`

## Internal Flow
1. Extract text using pdf-extract-text
2. Summarize using text-summarize
3. Translate using text-translate
```

### 模式 3: 通用工具（Universal Tool）

**定义**: 一个工具可以处理多种类型的任务，通过参数区分。

**经典案例**: Bash + 代码执行

**为什么需要通用工具**:
> LangChain: "不可能为每个操作都构建工具。Bash + 代码执行 = 通用工具，模型可以自主设计工具。"

**示例**:
```yaml
---
name: code-executor
description: Execute code in various languages (Python, JavaScript, Bash). Use for calculations, data processing, or any computational task.
---

# Code Executor

## Supported Languages
- Python
- JavaScript
- Bash

## Usage
\`\`\`bash
./scripts/exec.py --lang <language> --code "<code>"
\`\`\`

## Example
\`\`\`bash
./scripts/exec.py --lang python --code "print(2 ** 10)"
\`\`\`
```

**优点**:
- ✅ 灵活性极高
- ✅ 减少 tool count
- ✅ Agent 可以自主设计解决方案

**缺点**:
- ⚠️ 安全风险高（需要沙箱）
- ⚠️ 错误处理复杂

### 模式 4: 参数化工具（Parameterized Tool）

**定义**: 通过参数控制工具行为，实现一个工具多种用途。

**示例**:
```yaml
---
name: data-processor
description: Process data files with various operations (filter, sort, aggregate, transform). Use for data manipulation tasks.
---

# Data Processor

## Operations
- `filter`: Filter rows by condition
- `sort`: Sort by column
- `aggregate`: Group and aggregate
- `transform`: Apply transformations

## Usage
\`\`\`bash
./scripts/process.py <input-file> --operation <op> [options]
\`\`\`

## Examples
\`\`\`bash
# Filter
./scripts/process.py data.csv --operation filter --condition "age > 18"

# Sort
./scripts/process.py data.csv --operation sort --by "name" --order desc

# Aggregate
./scripts/process.py data.csv --operation aggregate --group-by "category" --agg "sum:value"
\`\`\`
```

**优点**:
- ✅ 一个工具覆盖多种场景
- ✅ 易于维护和测试
- ✅ 减少 tool count

**缺点**:
- ⚠️ 参数验证复杂
- ⚠️ 可能导致工具过于复杂

### 模式 5: 智能路由工具（Smart Router）

**定义**: 根据输入自动选择合适的处理方式。

**示例**:
```yaml
---
name: smart-file-reader
description: Automatically detect file type and use appropriate reader. Supports PDF, DOCX, TXT, JSON, CSV, etc. Use when you need to read any file without knowing its type.
---

# Smart File Reader

## Supported Formats
- Documents: PDF, DOCX, TXT
- Data: JSON, CSV, YAML
- Images: PNG, JPG (extracts metadata)

## Usage
\`\`\`bash
./scripts/read.sh <file-path>
\`\`\`

## How It Works
1. Detect file type by extension and content
2. Route to appropriate parser
3. Return unified format (text or structured data)
```

**优点**:
- ✅ Agent 不需要知道文件类型
- ✅ 简化 Agent 逻辑
- ✅ 更好的用户体验

**缺点**:
- ⚠️ 可能误判文件类型
- ⚠️ 难以处理边缘情况

---

## 🎨 工具接口设计最佳实践

### 1. 参数设计

**原则**:
- **最小惊讶原则**: 参数名和值应该符合直觉
- **提供默认值**: 减少必须参数的数量
- **类型明确**: 在文档中明确参数类型
- **验证输入**: 在脚本中验证参数合法性

**示例**:
```yaml
## Parameters
- `input` (required): Path to input file
- `output` (optional): Path to output file. Default: `<input>.out`
- `format` (optional): Output format (`json`|`csv`|`txt`). Default: `json`
- `verbose` (optional): Enable verbose output. Default: `false`

## Usage
\`\`\`bash
./scripts/process.sh <input> [--output <path>] [--format <fmt>] [--verbose]
\`\`\`
```

### 2. 结果格式

**原则**:
- **结构化输出**: 优先使用 JSON
- **包含元数据**: 时间戳、版本、状态等
- **错误信息清晰**: 包含错误代码和描述
- **可解析**: 易于 Agent 解析和处理

**好的结果格式**:
```json
{
  "success": true,
  "data": {
    "text": "Extracted text content...",
    "pages": 10,
    "words": 5000
  },
  "metadata": {
    "timestamp": "2026-03-18T20:00:00Z",
    "version": "1.0.0",
    "processing_time_ms": 150
  }
}
```

**错误格式**:
```json
{
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "Input file does not exist: /path/to/file.pdf",
    "details": {
      "path": "/path/to/file.pdf",
      "suggestion": "Check if the file path is correct"
    }
  }
}
```

### 3. 错误处理

**原则**:
- **优雅降级**: 不要让整个流程崩溃
- **提供替代方案**: 如果可能，提供备选路径
- **记录日志**: 记录详细日志供调试
- **Agent 可理解**: 错误信息应该让 Agent 能够理解和处理

**示例脚本**:
```bash
#!/bin/bash
set -euo pipefail

INPUT_FILE="$1"

# 检查文件是否存在
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "{
    \"success\": false,
    \"error\": {
      \"code\": \"FILE_NOT_FOUND\",
      \"message\": \"Input file does not exist: $INPUT_FILE\"
    }
  }"
  exit 1
fi

# 尝试处理文件
if ! OUTPUT=$(./scripts/process.py "$INPUT_FILE" 2>&1); then
  echo "{
    \"success\": false,
    \"error\": {
      \"code\": \"PROCESSING_ERROR\",
      \"message\": \"Failed to process file\",
      \"details\": \"$OUTPUT\"
    }
  }"
  exit 1
fi

# 成功
echo "{
  \"success\": true,
  \"data\": $OUTPUT
}"
```

---

## 🔒 工具安全性设计

### 1. 沙箱隔离

**原则**:
- **最小权限**: 只授予必要的权限
- **隔离执行**: 在沙箱中运行不受信任的代码
- **资源限制**: 限制 CPU、内存、时间
- **网络控制**: 限制网络访问

**OpenClaw 的沙箱机制**:
```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "docker": {
          "image": "ubuntu:22.04",
          "setupCommand": "apt-get update && apt-get install -y python3",
          "network": "none",
          "memory": "512m",
          "cpu": "0.5"
        }
      }
    }
  }
}
```

### 2. 输入验证

**原则**:
- **白名单优于黑名单**: 明确允许的内容，而不是禁止的内容
- **类型检查**: 验证参数类型
- **范围检查**: 验证数值范围
- **路径遍历**: 防止路径遍历攻击

**示例**:
```python
import os
import sys
from pathlib import Path

def validate_file_path(file_path: str) -> Path:
    """Validate file path to prevent traversal attacks."""
    path = Path(file_path).resolve()
    
    # 检查是否在工作目录内
    if not str(path).startswith(str(Path.cwd())):
        raise ValueError(f"Path outside workspace: {file_path}")
    
    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # 检查文件类型
    if path.suffix not in ['.pdf', '.txt', '.md']:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    
    return path
```

### 3. 密钥管理

**原则**:
- **不在代码中硬编码**: 使用环境变量或配置文件
- **不在日志中暴露**: 避免记录敏感信息
- **使用密钥管理服务**: 如 AWS Secrets Manager, HashiCorp Vault
- **定期轮换**: 定期更换密钥

**OpenClaw 的密钥注入**:
```json
{
  "skills": {
    "entries": {
      "my-api-tool": {
        "apiKey": {
          "source": "env",
          "provider": "default",
          "id": "MY_API_KEY"
        }
      }
    }
  }
}
```

**在技能中使用**:
```yaml
---
name: my-api-tool
description: Call external API with authentication
metadata:
  {
    "openclaw":
      {
        "requires": { "env": ["MY_API_KEY"] }
      }
  }
---

# My API Tool

The API key is automatically injected into the environment.

## Usage
\`\`\`bash
curl -H "Authorization: Bearer $MY_API_KEY" https://api.example.com/data
\`\`\`
```

---

## 📊 工具性能优化

### 1. 缓存策略

**原则**:
- **缓存不变结果**: 对于相同输入返回相同结果的工具
- **设置过期时间**: 避免缓存过期数据
- **缓存键设计**: 合理设计缓存键，避免冲突
- **缓存大小限制**: 避免内存溢出

**示例**:
```python
import hashlib
import json
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=128)
def process_file_cached(file_path: str, operation: str) -> dict:
    """Process file with caching."""
    # 检查文件是否被修改
    file_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()
    cache_key = f"{file_path}:{file_hash}:{operation}"
    
    # 检查缓存
    if cache_key in cache:
        return cache[cache_key]
    
    # 处理文件
    result = process_file(file_path, operation)
    
    # 存入缓存
    cache[cache_key] = result
    
    return result
```

### 2. 并行执行

**原则**:
- **识别独立任务**: 可以并行执行的任务
- **避免竞态条件**: 确保并行安全
- **限制并发数**: 避免资源耗尽
- **错误隔离**: 一个任务失败不影响其他任务

**示例**:
```python
import asyncio
import aiohttp

async def fetch_url(session, url):
    """Fetch a single URL."""
    async with session.get(url) as response:
        return await response.text()

async def fetch_all_urls(urls, max_concurrent=10):
    """Fetch multiple URLs in parallel."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_limit(session, url):
        async with semaphore:
            return await fetch_url(session, url)
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_with_limit(session, url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 3. 资源清理

**原则**:
- **及时释放资源**: 文件句柄、网络连接、临时文件
- **使用上下文管理器**: `with` 语句自动清理
- **异常安全**: 确保异常时也能清理资源

**示例**:
```python
import tempfile
from pathlib import Path

def process_large_file(file_path: str):
    """Process large file with proper resource cleanup."""
    # 使用临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=True) as tmp:
        # 处理文件
        with open(file_path, 'r') as f:
            for line in f:
                processed = process_line(line)
                tmp.write(processed)
        
        # 临时文件在 with 块结束时自动删除
        return tmp.name
```

---

## 🎓 实战案例：设计一个完整的工具

### 需求：网页内容提取工具

**功能要求**:
1. 输入：URL
2. 输出：提取的文本内容、标题、元数据
3. 支持：HTML, PDF
4. 特性：缓存、错误处理、超时控制

### 设计步骤

#### 步骤 1: 定义技能元数据

```yaml
---
name: web-content-extractor
description: Extract text content, title, and metadata from web pages or PDF URLs. Use when you need to read content from a web URL.
metadata:
  {
    "openclaw":
      {
        "emoji": "🌐",
        "requires": { "bins": ["curl", "python3"] },
        "install":
          [
            {
              "id": "pip",
              "kind": "pip",
              "packages": ["beautifulsoup4", "requests", "PyPDF2"],
              "label": "Install Python dependencies"
            }
          ]
      }
  }
---
```

#### 步骤 2: 编写核心脚本

**scripts/extract.py**:
```python
#!/usr/bin/env python3
import sys
import json
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import PyPDF2
import io

# 缓存配置
CACHE_DIR = Path.home() / ".cache" / "web-extractor"
CACHE_EXPIRY = 3600  # 1 hour

def get_cache_key(url: str) -> str:
    """Generate cache key from URL."""
    return hashlib.md5(url.encode()).hexdigest()

def get_cached(url: str) -> dict | None:
    """Get cached result if exists and not expired."""
    cache_key = get_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if not cache_file.exists():
        return None
    
    data = json.loads(cache_file.read_text())
    
    # 检查过期
    if time.time() - data['timestamp'] > CACHE_EXPIRY:
        cache_file.unlink()
        return None
    
    return data['result']

def set_cached(url: str, result: dict):
    """Cache the result."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = get_cache_key(url)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    data = {
        'url': url,
        'timestamp': time.time(),
        'result': result
    }
    
    cache_file.write_text(json.dumps(data, indent=2))

def extract_html(url: str) -> dict:
    """Extract content from HTML page."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 提取标题
    title = soup.find('title')
    title_text = title.get_text().strip() if title else ''
    
    # 提取主要内容
    # 尝试找到主要内容区域
    main_content = (
        soup.find('main') or 
        soup.find('article') or 
        soup.find('div', class_='content') or
        soup.find('body')
    )
    
    if main_content:
        # 移除脚本和样式
        for element in main_content(['script', 'style', 'nav', 'footer']):
            element.decompose()
        
        text = main_content.get_text(separator='\n', strip=True)
    else:
        text = soup.get_text(separator='\n', strip=True)
    
    # 提取元数据
    metadata = {}
    for meta in soup.find_all('meta'):
        name = meta.get('name') or meta.get('property')
        content = meta.get('content')
        if name and content:
            metadata[name] = content
    
    return {
        'title': title_text,
        'text': text,
        'metadata': metadata,
        'type': 'html',
        'url': url
    }

def extract_pdf(url: str) -> dict:
    """Extract content from PDF URL."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    pdf_file = io.BytesIO(response.content)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    
    text = ''
    for page in pdf_reader.pages:
        text += page.extract_text() + '\n'
    
    return {
        'title': Path(urlparse(url).path).stem,
        'text': text.strip(),
        'metadata': {
            'pages': len(pdf_reader.pages)
        },
        'type': 'pdf',
        'url': url
    }

def extract(url: str, use_cache: bool = True) -> dict:
    """Extract content from URL."""
    # 检查缓存
    if use_cache:
        cached = get_cached(url)
        if cached:
            return cached
    
    # 判断类型
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    try:
        if path.endswith('.pdf'):
            result = extract_pdf(url)
        else:
            result = extract_html(url)
        
        # 缓存结果
        if use_cache:
            set_cached(url, result)
        
        return result
    
    except Exception as e:
        return {
            'error': True,
            'message': str(e),
            'url': url
        }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: extract.py <url> [--no-cache]", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    use_cache = '--no-cache' not in sys.argv
    
    result = extract(url, use_cache)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

#### 步骤 3: 编写包装脚本

**scripts/extract.sh**:
```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/extract.py"

# 参数
URL="$1"
shift
ARGS="$@"

# 检查 Python 依赖
check_dependencies() {
    python3 -c "import bs4, requests, PyPDF2" 2>/dev/null || {
        echo "Installing dependencies..." >&2
        pip3 install beautifulsoup4 requests PyPDF2 --quiet
    }
}

# 主函数
main() {
    check_dependencies
    
    # 调用 Python 脚本
    python3 "$PYTHON_SCRIPT" "$URL" $ARGS
}

main
```

#### 步骤 4: 编写 SKILL.md

```yaml
---
name: web-content-extractor
description: Extract text content, title, and metadata from web pages or PDF URLs. Supports HTML and PDF formats with caching. Use when you need to read content from a web URL.
metadata:
  {
    "openclaw":
      {
        "emoji": "🌐",
        "requires": { "bins": ["curl", "python3"] }
      }
  }
---

# Web Content Extractor

Extract clean text content from web pages and PDF URLs.

## Features

- ✅ **HTML extraction**: Extracts main content, title, and metadata
- ✅ **PDF support**: Downloads and extracts text from PDF URLs
- ✅ **Smart caching**: Caches results for 1 hour to avoid repeated requests
- ✅ **Error handling**: Clear error messages for debugging
- ✅ **Timeout control**: 30-second timeout for requests

## Usage

### Basic Usage

\`\`\`bash
./scripts/extract.sh <url>
\`\`\`

### Skip Cache

\`\`\`bash
./scripts/extract.sh <url> --no-cache
\`\`\`

## Output Format

\`\`\`json
{
  "title": "Page Title",
  "text": "Extracted text content...",
  "metadata": {
    "description": "Page description",
    "author": "Author name"
  },
  "type": "html",
  "url": "https://example.com"
}
\`\`\`

## Error Handling

If extraction fails, the output will be:

\`\`\`json
{
  "error": true,
  "message": "Error description",
  "url": "https://example.com"
}
\`\`\`

## Examples

### Extract from HTML page

\`\`\`bash
./scripts/extract.sh https://example.com/article
\`\`\`

### Extract from PDF

\`\`\`bash
./scripts/extract.sh https://example.com/document.pdf
\`\`\`

### Force refresh (skip cache)

\`\`\`bash
./scripts/extract.sh https://example.com --no-cache
\`\`\`

## Notes

- Results are cached for 1 hour in `~/.cache/web-extractor/`
- Timeout is set to 30 seconds per request
- For PDFs, all pages are extracted and combined
- For HTML, the script tries to find the main content area

## See Also

- [API Reference](references/api-reference.md)
- [Advanced Examples](references/examples.md)
```

#### 步骤 5: 编写参考文档

**references/api-reference.md**:
```markdown
# API Reference

## extract.py

### Usage

\`\`\`bash
python3 extract.py <url> [--no-cache]
\`\`\`

### Arguments

- `url` (required): The URL to extract content from
- `--no-cache` (optional): Skip cache and fetch fresh content

### Return Value

JSON object with the following fields:

- `title` (string): Page title
- `text` (string): Extracted text content
- `metadata` (object): Metadata from meta tags
- `type` (string): Content type (`html` or `pdf`)
- `url` (string): Original URL

### Error Handling

On error, returns:

\`\`\`json
{
  "error": true,
  "message": "Error description",
  "url": "https://example.com"
}
\`\`\`

## Cache Management

### Cache Location

`~/.cache/web-extractor/`

### Cache Format

Each cached result is stored as a JSON file:

\`\`\`json
{
  "url": "https://example.com",
  "timestamp": 1234567890,
  "result": {
    "title": "...",
    "text": "...",
    "metadata": {}
  }
}
\`\`\`

### Clearing Cache

\`\`\`bash
rm -rf ~/.cache/web-extractor/
\`\`\`
```

---

## 🚀 工具设计清单

### 设计前

- [ ] **明确需求**: 工具要解决什么问题？
- [ ] **定义范围**: 工具的边界在哪里？
- [ ] **考虑复用**: 是否已有类似工具？
- [ ] **评估风险**: 有哪些安全风险？

### 设计中

- [ ] **单一职责**: 工具是否只做一件事？
- [ ] **清晰接口**: 参数和返回值是否清晰？
- [ ] **错误处理**: 是否优雅处理错误？
- [ ] **文档完善**: 是否有清晰的文档？
- [ ] **性能考虑**: 是否需要缓存或并行？
- [ ] **安全设计**: 是否有输入验证和沙箱？

### 实现后

- [ ] **单元测试**: 是否有测试覆盖？
- [ ] **集成测试**: 是否测试与 Agent 的集成？
- [ ] **性能测试**: 是否测试性能？
- [ ] **安全审计**: 是否进行安全审查？
- [ ] **用户反馈**: 是否收集用户反馈？

---

## 📚 参考资源

### 官方文档

- **AgentSkills 规范**: https://agentskills.io/specification
- **OpenClaw 技能系统**: `~/.openclaw/docs/tools/skills.md`
- **LangChain Agent Harness**: https://blog.langchain.dev/the-anatomy-of-an-agent-harness/

### 相关项目

- **gstack**: Garry Tan 的角色化工具集（10 个定制工具）
- **Anthropic Skills**: 文档处理工具（docx, pdf, pptx, xlsx）
- **Pi Skills**: Web 搜索、浏览器自动化、Google APIs

### 理论框架

- **Lilian Weng - LLM Powered Autonomous Agents**: Planning + Memory + Tool use
- **LangChain - Agent Harness**: Model + Harness = Agent
- **OpenAI - Function Calling**: 工具调用的标准化接口

---

## 💡 核心洞察

### 1. 工具是 Agent 能力的延伸

> Model + Tools = Agent
> 模型（智能） + 工具（能力） = 智能体

工具不是可有可无的附加品，而是 Agent 的核心组成部分。好的工具设计可以显著提升 Agent 的能力边界。

### 2. 渐进式披露是关键

不要在每次对话中都加载完整指令。通过描述匹配 + 按需加载，可以节省大量 token 并提升性能。

### 3. 安全性不能妥协

工具可以指示模型执行任何操作，因此必须：
- 在沙箱中运行不受信任的代码
- 验证所有输入
- 使用最小权限原则
- 定期审计和更新

### 4. 文档是最好的 API

Agent 通过阅读文档来理解如何使用工具。因此：
- 描述必须清晰、具体、包含触发条件
- 提供完整的使用示例
- 说明输出格式和错误处理
- 添加参考文档供深入了解

### 5. 工具设计是工程 + 艺术

好的工具设计需要：
- **工程思维**: 单一职责、接口清晰、错误处理
- **艺术感觉**: 用户体验、文档编写、示例设计

---

## 🎯 下一步探索方向

1. **多工具编排**: 如何设计工具链和工具选择策略？
2. **工具学习**: Agent 如何自动学习使用新工具？
3. **工具测试**: 如何系统地测试工具与 Agent 的集成？
4. **工具优化**: 如何根据使用数据优化工具设计？
5. **工具生态**: 如何构建和维护工具生态系统？

---

## 📝 总结

本次深度探索了 AI Agent 工具设计的核心模式、最佳实践和实际案例。

**核心收获**:
1. 理解了 AgentSkills 规范和 OpenClaw 技能系统
2. 掌握了 5 种核心工具设计模式
3. 学习了工具接口设计、安全性、性能优化的最佳实践
4. 通过实战案例完整设计了网页内容提取工具
5. 建立了工具设计的系统化思维

**应用价值**:
- 可以设计高质量、可维护、安全的 Agent 工具
- 理解如何优化工具性能和用户体验
- 掌握工具与 Agent 集成的关键要点

**启发**:
- 工具设计是 AI Agent 开发的核心技能
- 好的工具设计需要工程 + 艺术的结合
- 文档和示例与代码同等重要

---

**探索时间**: 2026-03-18 20:00 - 21:30 (1.5 小时)
**笔记字数**: ~15,000 字
**相关文件**: 
- `memory/exploration-notes/2026-03-18-agent-self-evolution.md` (Agent 自我进化)
- `memory/exploration-notes/lightweight-log.md` (轻量级探索日志)

---

*工具是 Agent 的手脚，好的工具设计让 Agent 更强大、更安全、更可靠。*
