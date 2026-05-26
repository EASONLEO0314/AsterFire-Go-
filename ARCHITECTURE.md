# AI 智能简历分析系统 — 标准化工程架构设计文档

> 运行环境：阿里云函数计算 FC Serverless | 语言：Python 3.10+ | 接口：RESTful | 交付：24h

---

## 一、功能模块拆解与验收标准

### 模块一：简历上传与解析（必选）

| 子功能 | 描述 | 验收标准 |
|--------|------|---------|
| 1.1 PDF 文件接收 | `multipart/form-data` 单文件上传 | 仅允许 `.pdf`，拒绝其他格式 |
| 1.2 文件校验 | 大小 ≤10MB，页数 ≤10 页 | 超限返回错误码 2 + 明确提示 |
| 1.3 PDF 文本提取 | PyPDF2 逐页提取原始文本 | 提取结果包含总页数 |
| 1.4 文本清洗 | 去乱码/控制字符/多余空行，保留段落结构 | 清洗后文本可读，无明显 `\x00` 等噪音 |
| 1.5 生成 resumeId | UUID v4，作为后续接口的简历标识 | 全局唯一 |
| 1.6 输出 | `{resumeId, fileName, pages, cleanedText}` | 字段完整，类型正确 |

### 模块二：关键信息 AI 提取（必选 + 加分）

| 子功能 | 描述 | 验收标准 |
|--------|------|---------|
| 2.1 必选字段提取 | 姓名/电话/邮箱/地址 | 四字段全部提取，缺失为 `null` |
| 2.2 加分-求职信息 | 求职意向/期望薪资 | 缺失为 `null` |
| 2.3 加分-工作年限 | 数字或范围 | 缺失为 `null` |
| 2.4 加分-学历背景 | `{degree, school, major, graduationYear}` | 四子字段结构化 |
| 2.5 加分-项目经历 | `[{name, role, techStack}]` | 数组格式，无则为 `[]` |
| 2.6 AI 调用容错 | 超时 30s，重试 2 次 | 超时返回错误码 3 |
| 2.7 输出 | 完整结构化 JSON | 字段齐全，null 值明确 |

### 模块三：简历评分与岗位匹配（必选 + 加分）

| 子功能 | 描述 | 验收标准 |
|--------|------|---------|
| 3.1 接收岗位描述 | 纯文本，≤5000 字符 | 空文本返回错误码 1 |
| 3.2 AI 技能匹配 | 简历技能 vs 岗位要求 | 返回 0-100 技能匹配率 |
| 3.3 AI 经验匹配 | 工作年限/项目 vs 岗位要求 | 返回 0-100 经验相关性 |
| 3.4 AI 学历匹配 | 学历/专业 vs 岗位要求 | 返回 0-100 学历匹配度 |
| 3.5 综合评分 | 加权计算或 AI 综合评判 | 0-100 综合分 |
| 3.6 加分-匹配理由 | AI 生成匹配分析文本 | `summary` 字段 |
| 3.7 加分-优势/缺失 | AI 提取优势点 + 缺失关键词 | `strengths[]`, `missingKeywords[]` |

### 模块四：结果返回与缓存（必选 + 加分）

| 子功能 | 描述 | 验收标准 |
|--------|------|---------|
| 4.1 统一 JSON 返回 | `{code, msg, data}` 格式 | 所有接口一致 |
| 4.2 内存缓存 | `dict[md5] → {parsed/extract/match}` | 命中缓存时跳过重复处理 |
| 4.3 缓存失效 | 24h TTL，惰性淘汰 | 过期数据不返回 |
| 4.4 加分-Redis 缓存 | 可选 Redis 作为二级缓存 | `REDIS_URL` 环境变量控制 |

### 模块五：前端页面（必选）

| 子功能 | 描述 | 验收标准 |
|--------|------|---------|
| 5.1 简历上传 | 拖拽/点击上传 PDF | 文件类型校验 + 大小校验 |
| 5.2 解析展示 | 显示清洗文本 + 结构化信息 | 信息展示清晰 |
| 5.3 岗位输入 | 文本输入框 | 支持多行文本 |
| 5.4 评分可视化 | 环形图/进度条展示分项得分 | 四个指标直观可视化 |
| 5.5 部署 | GitHub Pages | 提供可访问 URL |

---

## 二、项目目录结构（FC Serverless 分层架构）

```
Sidereus AI/
├── app.py                        # FC 入口，Flask 应用工厂，路由注册
├── requirements.txt              # Python 依赖清单
├── README.md                     # 部署说明 + 接口文档 + 环境变量
├── ARCHITECTURE.md               # 本架构文档
│
├── src/                          # 核心源码（分层架构）
│   ├── __init__.py
│   ├── config.py                 # 全局配置：环境变量、常量、阈值
│   │
│   ├── utils/                    # ========== 工具层 ==========
│   │   ├── __init__.py
│   │   └── file_utils.py         # 文件类型校验、大小检查、MD5 计算
│   │
│   ├── parser/                   # ========== 解析层 ==========
│   │   ├── __init__.py
│   │   └── pdf_parser.py         # PyPDF2 提取文本、文本清洗管道
│   │
│   ├── ai_service/               # ========== AI 服务层 ==========
│   │   ├── __init__.py
│   │   ├── client.py             # DashScope SDK 封装：调用、超时、重试
│   │   ├── extractor.py          # 关键信息提取 Prompt + 结果解析
│   │   └── matcher.py            # 岗位匹配 Prompt + 评分结构化
│   │
│   ├── cache/                    # ========== 缓存层 ==========
│   │   ├── __init__.py
│   │   └── cache_manager.py      # 内存字典缓存 + 可选 Redis 二级缓存
│   │
│   ├── routes/                   # ========== 路由层 ==========
│   │   ├── __init__.py
│   │   ├── upload.py             # POST /api/resume/upload
│   │   ├── extract.py            # POST /api/resume/extract
│   │   └── match.py              # POST /api/match
│   │
│   └── exceptions/               # ========== 异常处理层 ==========
│       ├── __init__.py
│       └── handler.py            # 自定义异常类、全局错误处理器
│
└── frontend/                     # 前端（独立部署到 GitHub Pages）
    ├── index.html                # 单页入口
    ├── app.js                    # Vue 3 CDN 应用逻辑
    └── style.css                 # 样式（响应式）
```

### 分层职责说明

| 层级 | 目录 | 职责 | 依赖方向 |
|------|------|------|---------|
| 入口层 | `app.py` | Flask 应用创建、蓝图注册、CORS 配置 | → 路由层 + 异常层 |
| 路由层 | `src/routes/` | 参数校验、流程编排、响应封装 | → 解析层 + AI 层 + 缓存层 |
| AI 服务层 | `src/ai_service/` | Prompt 模板、AI 调用、结果反序列化 | → 工具层 |
| 解析层 | `src/parser/` | PDF→文本、清洗管道 | → 工具层 |
| 缓存层 | `src/cache/` | MD5 索引、TTL 管理、可选 Redis | 无外部依赖 |
| 工具层 | `src/utils/` | 文件校验、哈希计算 | 无外部依赖 |
| 异常层 | `src/exceptions/` | 自定义异常、全局 Flask errorhandler | 无外部依赖 |
| 配置 | `src/config.py` | 环境变量、常量 | 被所有层读取 |

---

## 三、RESTful 接口定义

### 3.1 `POST /api/resume/upload` — 简历上传与解析

**请求**
```
Method:  POST
Content-Type: multipart/form-data
Body:
  file: <PDF 二进制文件>  (required, .pdf, ≤10MB)
```

**成功响应 (200)**
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-...",
    "fileName": "张三简历.pdf",
    "pages": 3,
    "cleanedText": "姓名：张三\n电话：13800138000\n..."
  }
}
```

**错误码**

| code | msg | 触发条件 |
|------|-----|---------|
| 1 | 请上传 PDF 文件 | 未传 file 字段 |
| 2 | 仅支持 PDF 格式 | 文件后缀非 `.pdf` |
| 2 | 文件大小超过 10MB 限制 | 文件 > 10MB |
| 2 | PDF 解析失败，文件可能已损坏 | PyPDF2 抛出异常 |
| 2 | PDF 页数超过 10 页限制 | 页数 > 10 |
| 4 | 服务器内部错误 | 其他未预期异常 |

---

### 3.2 `POST /api/resume/extract` — AI 关键信息提取

**请求**
```
Method:  POST
Content-Type: application/json
Body:
{
  "resumeId": "a1b2c3d4-...",      // required, 上传接口返回的 ID
  "text": "可选，直接传入简历文本"    // optional, 跳过 resumeId 查缓存
}
```

**成功响应 (200)**
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-...",
    "name": "张三",
    "phone": "13800138000",
    "email": "zhangsan@example.com",
    "address": "北京市海淀区",
    "jobIntention": "高级前端工程师",
    "expectedSalary": "25K-35K",
    "workYears": 5,
    "education": {
      "degree": "本科",
      "school": "清华大学",
      "major": "计算机科学与技术",
      "graduationYear": 2019
    },
    "projects": [
      {
        "name": "电商平台重构",
        "role": "前端负责人",
        "techStack": ["Vue3", "TypeScript", "Vite"]
      }
    ]
  }
}
```

**错误码**

| code | msg | 触发条件 |
|------|-----|---------|
| 1 | 请提供 resumeId 或 text | 两者均为空 |
| 1 | 指定 resumeId 对应的简历不存在 | resumeId 无效 |
| 3 | AI 提取超时，请稍后重试 | 超时 + 重试耗尽 |
| 4 | AI 返回格式异常 | 模型返回无法解析 |

---

### 3.3 `POST /api/match` — 简历与岗位匹配评分

**请求**
```
Method:  POST
Content-Type: application/json
Body:
{
  "resumeId": "a1b2c3d4-...",                          // required
  "jobDescription": "岗位职责：负责前端架构设计...要求：5年以上经验，本科及以上..."  // required
}
```

**成功响应 (200)**
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-...",
    "totalScore": 85,
    "skillMatch": 90,
    "experienceMatch": 80,
    "educationMatch": 100,
    "strengths": [
      "技能栈与岗位高度匹配",
      "有电商项目经验，与业务场景一致"
    ],
    "missingKeywords": ["Node.js", "React"],
    "summary": "该候选人整体匹配度较高，前端技能扎实，电商背景与岗位需求吻合。建议重点考察 Node.js 后端能力和 React 技术栈的迁移能力。"
  }
}
```

**错误码**

| code | msg | 触发条件 |
|------|-----|---------|
| 1 | 请提供 resumeId 和 jobDescription | 参数缺失 |
| 1 | resumeId 对应的简历不存在 | resumeId 无效 |
| 1 | 请先完成简历信息提取 | 缓存中无 extract 结果 |
| 3 | AI 评分超时，请稍后重试 | 超时 + 重试耗尽 |
| 4 | AI 返回格式异常 | 模型返回无法解析 |

---

## 四、数据结构定义（JSON Schema）

### 4.1 简历解析结果 `ParsedResume`
```json
{
  "$schema": "ParsedResume",
  "resumeId": "string (UUID v4)",
  "fileName": "string",
  "pages": "integer (1-10)",
  "cleanedText": "string (清洗后纯文本)",
  "createdAt": "integer (Unix timestamp, 缓存使用)"
}
```

### 4.2 AI 提取结果 `ExtractedInfo`
```json
{
  "$schema": "ExtractedInfo",
  "resumeId": "string",
  "name": "string | null",
  "phone": "string | null",
  "email": "string | null",
  "address": "string | null",
  "jobIntention": "string | null",
  "expectedSalary": "string | null",
  "workYears": "number | null",
  "education": {
    "degree": "string | null",
    "school": "string | null",
    "major": "string | null",
    "graduationYear": "number | null"
  },
  "projects": [
    {
      "name": "string",
      "role": "string",
      "techStack": ["string"]
    }
  ]
}
```

### 4.3 匹配结果 `MatchResult`
```json
{
  "$schema": "MatchResult",
  "resumeId": "string",
  "totalScore": "integer (0-100)",
  "skillMatch": "integer (0-100)",
  "experienceMatch": "integer (0-100)",
  "educationMatch": "integer (0-100)",
  "strengths": ["string"],
  "missingKeywords": ["string"],
  "summary": "string"
}
```

### 4.4 统一响应信封 `ApiResponse`
```json
{
  "$schema": "ApiResponse",
  "code": "integer (0|1|2|3|4)",
  "msg": "string",
  "data": "ParsedResume | ExtractedInfo | MatchResult | null"
}
```

### 4.5 缓存数据结构 `CacheEntry`
```json
{
  "$schema": "CacheEntry",
  "md5": "string (文件 MD5)",
  "resumeId": "string",
  "parsed": "ParsedResume | null",
  "extracted": "ExtractedInfo | null",
  "matched": "Map<string, MatchResult> (key=jobDescription MD5)",
  "createdAt": "integer (Unix timestamp)",
  "ttl": 86400
}
```

---

## 五、技术方案选型

### 5.1 AI 模型调用方案

| 项目 | 选型 | 说明 |
|------|------|------|
| 模型服务 | 通义千问 DashScope | 阿里云原生，低延迟，FC 内网互通 |
| SDK | `dashscope>=1.20` | 官方 Python SDK |
| 默认模型 | `qwen-plus` | 性价比最优，支持结构化输出 |
| 备选模型 | `qwen-turbo`（更快）/ `qwen-max`（更强） | 通过 `AI_MODEL` 环境变量切换 |
| 超时 | 30 秒 | HTTP 层 + SDK 层双保险 |
| 重试 | 最多 2 次，指数退避（1s → 2s） | 仅重试网络错误/超时，不重试 4xx |
| 兼容方案 | OpenAI 兼容接口 | 备选，适配不同云平台 |

**Prompt 设计策略：**

- **提取**：System Prompt 设定为 "JSON 提取器" 角色，要求严格输出 JSON，字段缺失填 null
- **匹配**：System Prompt 设定为 "招聘评估专家" 角色，要求分维度打分 + 结构化输出
- 两个 Prompt 均包含 `response_format: {type: "json_object"}` 约束

### 5.2 缓存方案

```
请求流入
    │
    ▼
┌──────────────────┐
│  计算文件 MD5     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐    命中 ──▶ 直接返回缓存数据
│  L1: 内存字典      │
│  key=MD5          │
│  TTL=24h          │
└──────┬───────────┘
       │ 未命中
       ▼
┌──────────────────┐
│  执行解析/AI调用   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  写入 L1 内存      │
│  (可选) 写入 Redis │
└──────────────────┘
```

**设计要点：**

| 项目 | 内存缓存 (L1) | Redis 缓存 (L2, 可选) |
|------|-------------|---------------------|
| 数据结构 | `dict[str, CacheEntry]` | String (JSON 序列化) |
| 并发安全 | `threading.Lock` | Redis 单线程原子操作 |
| TTL 策略 | 惰性淘汰（读取时检查） | Redis `EXPIRE` 命令 |
| 启用条件 | 始终启用 | `REDIS_URL` 环境变量存在时启用 |
| FC 适用性 | 实例内有效，跨实例不共享 | 跨实例共享，冷启动友好 |

### 5.3 异常处理方案

**自定义异常类层次：**

```
AppException (基类, code + message)
  ├── ParamError (code=1)     — 参数缺失/格式错误
  ├── FileError (code=2)      — 非PDF/超大/损坏/页数超限
  ├── AITimeoutError (code=3) — AI 调用超时/重试耗尽
  └── ServerError (code=4)    — 其他未预期异常
```

**Flask 全局异常拦截：**

```python
@app.errorhandler(AppException)
def handle_app_error(e):
    return {"code": e.code, "msg": e.message, "data": None}, 200

@app.errorhandler(Exception)
def handle_unknown(e):
    # 记录日志，返回通用错误
    return {"code": 4, "msg": "服务器内部错误", "data": None}, 200
```

**注意**：业务异常统一返回 HTTP 200，通过 `code` 区分成败，方便前端统一处理。

---

## 六、接口调用流程

### 完整三步骤流程
```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  UPLOAD  │───▶│ EXTRACT  │───▶│  MATCH   │
│  上传解析  │    │ AI 提取   │    │ 岗位匹配   │
└──────────┘    └──────────┘    └──────────┘
     │               │               │
     ▼               ▼               ▼
  resumeId      结构化信息        评分结果
```

### 前端交互流程
```
[上传 PDF] → [展示解析文本] → [AI 提取] → [展示结构化卡片]
                                                │
                                                ▼
                               [输入岗位描述] → [匹配评分] → [可视化图表]
```

---

## 七、部署架构

```
┌──────────────────────────────────────────────────┐
│                  GitHub Pages                      │
│              前端静态页面 (HTTPS)                    │
│         https://<user>.github.io/resume-ai         │
└──────────────────────┬───────────────────────────┘
                       │ HTTPS (CORS enabled)
                       ▼
┌──────────────────────────────────────────────────────┐
│         阿里云函数计算 FC (HTTP 触发器)                │
│         Python 3.10 运行时                            │
│  ┌──────────────────────────────────────────────┐   │
│  │             Flask WSGI 应用                    │   │
│  │  /api/resume/upload                           │   │
│  │  /api/resume/extract                          │   │
│  │  /api/match                                   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  可选: Redis 实例 (内网连接, 缓存共享)                 │
└──────────────────────────────────────────────────────┘
```

---

## 八、开发顺序建议

| 阶段 | 内容 | 预估耗时 |
|------|------|---------|
| 1 | `config.py` + `exceptions/` + `utils/` | 0.5h |
| 2 | `parser/pdf_parser.py` | 1h |
| 3 | `ai_service/client.py` + `extractor.py` | 2h |
| 4 | `ai_service/matcher.py` | 1.5h |
| 5 | `cache/cache_manager.py` | 1h |
| 6 | `routes/` 三个接口 + `app.py` | 2h |
| 7 | 联调自检 (本地 Flask 跑通三接口) | 1h |
| 8 | `frontend/` (HTML + Vue + CSS) | 3h |
| 9 | FC 部署 + GitHub Pages 部署 | 2h |
| 10 | README + 最终自检 | 1h |

> 总计估算：~15h，24h 交付时限内有余量。
