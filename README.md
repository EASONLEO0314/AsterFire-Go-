# AI 智能简历分析系统

> **赛事极速开发项目** | 阿里云 Serverless + Python + AI | 24 小时交付

基于通义千问大模型的智能简历分析系统，支持 PDF 简历上传解析、AI 关键信息提取、岗位匹配评分的全流程自动化，适配阿里云函数计算 FC Serverless 部署。

---

## 功能模块

| 模块 | 功能 | 状态 |
|------|------|:----:|
| 简历上传解析 | PDF 上传 → 文本提取 → 五步清洗管道，≤10MB/≤10页 | 必选 |
| 扫描版 PDF OCR | 文字型 PDF 提取失败时自动降级为 VL 多模态 OCR 识别 | 加分 |
| AI 信息提取 | 姓名/电话/邮箱/地址 + 求职意向/薪资/年限/学历/项目 | 必选 + 加分 |
| 岗位匹配评分 | 四维评分（综合/技能/经验/学历）+ 优势 + 缺失关键词 | 必选 + 加分 |
| 结果缓存 | 内存字典 24h TTL + 可选 Redis 二级缓存 + 惰性淘汰 | 必选 + 加分 |
| 前端页面 | Vue 3 单页应用，SVG 环形图可视化，部署 GitHub Pages | 必选 |

---

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| 运行时 | Python 3.9+ / Flask 3.x |
| 云平台 | 阿里云函数计算 FC (HTTP 触发器) |
| AI 模型 | 通义千问 DashScope (qwen-plus) + Qwen-VL 多模态 OCR |
| PDF 解析 | PyPDF2 + PyMuPDF（扫描版 OCR 降级） |
| 缓存 | 内存 dict + 可选 Redis 5.x |
| 前端 | Vue 3 CDN + 原生 CSS |
| WSGI | Gunicorn (本地) / FC 内置 |

---

## 目录结构

```
Sidereus AI/
├── app.py                        # FC 入口，Flask 应用工厂
├── requirements.txt              # Python 依赖清单
├── README.md                     # 部署说明 + 接口文档
├── ARCHITECTURE.md               # 详细架构设计文档
│
├── src/                          # 核心源码（七层架构）
│   ├── config.py                 # 全局配置、环境变量、日志
│   ├── utils/                    # 工具层：文件校验、JSON 解析
│   ├── parser/                   # 解析层：PDF 提取、文本清洗
│   ├── ai_service/               # AI 服务层：调用、提取、匹配
│   ├── cache/                    # 缓存层：内存 + Redis
│   ├── routes/                   # 路由层：上传/提取/匹配/查询
│   └── exceptions/               # 异常层：分级错误码 + 全局拦截
│
└── frontend/                     # 前端（独立部署）
    ├── index.html                # Vue 3 SPA 入口
    ├── app.js                    # 应用逻辑
    └── style.css                 # 响应式样式
```

### 分层架构与依赖方向

```
入口层 (app.py) → 路由层 (routes/) → AI服务层 (ai_service/) → 工具层 (utils/)
                   ↓                  ↓
                 缓存层 (cache/)    解析层 (parser/)
                   ↓                  ↓
              异常层 (exceptions/) ← 所有上层
```

---

## 快速开始

### 1. 环境要求

- Python 3.9+
- pip

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 必须：DashScope API Key（阿里云百炼平台获取）
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxx"

# 可选配置
export AI_MODEL="qwen-plus"          # 模型选择：qwen-turbo / qwen-plus / qwen-max
export LOG_LEVEL="INFO"              # 日志级别：DEBUG / INFO / WARNING / ERROR
export AI_FALLBACK_ENABLED="1"       # AI 失败时是否启用正则降级（1=启用，0=关闭）
export REDIS_URL="redis://..."       # Redis 连接地址（可选，不配则仅使用内存缓存）
export VL_MODEL="qwen-vl-plus"       # 多模态 OCR 模型：qwen-vl-plus / qwen-vl-max
export OCR_ENABLED="1"               # 是否启用扫描版 PDF OCR 降级（1=启用，0=关闭）
export OCR_DPI="200"                 # PDF 渲染清晰度（150-300，越高越清晰但文件越大）
```

### 4. 本地运行

```bash
# 开发模式
python app.py

# 生产模式 (Gunicorn)
gunicorn app:app -w 2 -b 0.0.0.0:5000 --timeout 60
```

服务启动后访问 `http://localhost:5000` 查看前端页面，`http://localhost:5000/api/health` 检查服务状态。

---

## 部署到阿里云函数计算 FC

### 前置准备

1. 开通[阿里云函数计算 FC](https://fc.console.aliyun.com/)
2. 开通[阿里云百炼平台](https://bailian.console.aliyun.com/) 获取 DashScope API Key
3. （可选）开通[阿里云 Redis](https://redis.console.aliyun.com/) 实例

### 部署步骤

**1. 准备部署包**

```bash
# 安装依赖到项目目录
pip install -r requirements.txt -t ./vendor

# 打包（包含 vendor 目录和所有源码）
zip -r deploy.zip app.py src/ vendor/
```

**2. 创建 FC 函数**

- 运行时：Python 3.9 / 3.10
- 触发器：HTTP 触发器（认证方式：anonymous）
- 请求处理：`app.app`（Flask 应用实例）
- 内存：512 MB（推荐）
- 超时：120 秒

**3. 上传部署包**

通过 FC 控制台上传 `deploy.zip` 或使用 Serverless Devs / Terraform。

**4. 配置环境变量**

在 FC 函数配置中添加：

| 变量名 | 必填 | 说明 |
|--------|:----:|------|
| `DASHSCOPE_API_KEY` | 是 | 通义千问 API Key |
| `AI_MODEL` | 否 | 模型名称，默认 qwen-plus |
| `AI_FALLBACK_ENABLED` | 否 | AI 降级开关，默认 1 |
| `VL_MODEL` | 否 | 多模态 OCR 模型，默认 qwen-vl-plus |
| `OCR_ENABLED` | 否 | 扫描版 PDF OCR 降级开关，默认 1 |
| `OCR_DPI` | 否 | PDF 渲染清晰度，默认 200 |
| `LOG_LEVEL` | 否 | 日志级别，默认 INFO |
| `REDIS_URL` | 否 | Redis 连接地址，不配则仅内存缓存 |

**5. 验证部署**

```bash
curl https://<your-fc-domain>/api/health
# {"code":0,"msg":"ok","data":{"status":"healthy","timestamp":...}}
```

---

## 前端部署到 GitHub Pages

1. 将 `frontend/` 目录推送到 GitHub 仓库的 `gh-pages` 分支（或配置 `main` 分支的 `/docs` 目录）

2. 修改 [frontend/app.js](frontend/app.js#L5) 中的 `API_BASE` 为 FC 后端域名：

```javascript
const API_BASE = 'https://<your-fc-domain>'
```

3. 启用 GitHub Pages：`Settings → Pages → Source → Deploy from branch → gh-pages`

4. 前端线上地址：`https://<your-username>.github.io/<repo-name>/`

---

## 接口文档

所有接口统一返回格式：

```json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
```

### 错误码一览

| code | 含义 | 触发场景 |
|:----:|------|---------|
| 0 | 成功 | 正常返回 |
| 1 | 参数错误 | 缺少必填参数 / 格式校验失败 / resumeId 无效 |
| 2 | 文件错误 | 非 PDF 格式 / 超过 10MB / 超过 10 页 / 损坏 / 扫描图片型 |
| 3 | AI 超时 | AI 调用超时或限流，重试耗尽 |
| 4 | 服务器错误 | 未配置 API Key / AI 返回格式异常 / 其他未预期错误 |

---

### 1. 健康检查

**`GET /api/health`**

请求示例：
```bash
curl http://localhost:5000/api/health
```

返回示例：
```json
{
  "code": 0,
  "msg": "ok",
  "data": { "status": "healthy", "timestamp": 1716652800 }
}
```

---

### 2. 简历上传解析

**`POST /api/resume/upload`**

请求示例：
```bash
curl -X POST http://localhost:5000/api/resume/upload \
  -F "file=@张三简历.pdf"
```

返回示例：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "fileName": "张三简历.pdf",
    "pages": 3,
    "cleanedText": "姓名：张三\n电话：13800138000\n邮箱：zhangsan@example.com\n...",
    "md5": "d41d8cd98f00b204e9800998ecf8427e"
  }
}
```

错误响应：
```json
{ "code": 2, "msg": "仅支持 PDF 格式，当前上传为 .docx", "data": null }
{ "code": 2, "msg": "文件大小超过 10MB 限制", "data": null }
{ "code": 2, "msg": "PDF 页数超过 10 页限制，当前 15 页", "data": null }
{ "code": 2, "msg": "PDF 文本提取为空，OCR 识别亦未能提取到文字", "data": null }
```

---

### 3. AI 关键信息提取

**`POST /api/resume/extract`**

请求示例：
```bash
curl -X POST http://localhost:5000/api/resume/extract \
  -H "Content-Type: application/json" \
  -d '{"resumeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'
```

返回示例：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
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

错误响应：
```json
{ "code": 1, "msg": "指定 resumeId 对应的简历不存在或已过期，请重新上传", "data": null }
{ "code": 1, "msg": "请提供 resumeId 或 text 参数", "data": null }
{ "code": 3, "msg": "AI 服务超时，已重试仍失败，请稍后重试", "data": null }
{ "code": 4, "msg": "AI 服务未配置，请设置 DASHSCOPE_API_KEY 环境变量", "data": null }
```

> **设计要点**：缺失字段返回 `null` 而非空字符串；已提取过的 resumeId 请求会命中缓存直接返回。

---

### 4. 简历岗位匹配评分

**`POST /api/match`**

请求示例：
```bash
curl -X POST http://localhost:5000/api/match \
  -H "Content-Type: application/json" \
  -d '{
    "resumeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "jobDescription": "招聘高级前端工程师，要求5年以上经验，精通Vue3/TypeScript，本科及以上学历"
  }'
```

返回示例：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "totalScore": 85,
    "skillMatch": 90,
    "experienceMatch": 80,
    "educationMatch": 100,
    "strengths": ["技能栈与岗位高度匹配", "有电商项目经验"],
    "missingKeywords": ["Node.js", "React"],
    "summary": "整体匹配度较高，前端技能扎实，建议重点考察后端能力。"
  }
}
```

错误响应：
```json
{ "code": 1, "msg": "请提供 resumeId", "data": null }
{ "code": 1, "msg": "请提供 jobDescription 岗位描述", "data": null }
{ "code": 1, "msg": "指定 resumeId 对应的简历不存在或已过期", "data": null }
{ "code": 1, "msg": "请先完成简历信息提取（调用 /api/resume/extract）", "data": null }
{ "code": 3, "msg": "AI 服务超时，已重试仍失败，请稍后重试", "data": null }
```

> **设计要点**：同一 resumeId 对相同岗位描述的匹配结果会被缓存，再次请求直接返回缓存。

---

### 5. 综合查询

**`GET /api/resume/<resume_id>`**

请求示例：
```bash
curl http://localhost:5000/api/resume/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

返回示例：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "resumeId": "a1b2c3d4-...",
    "status": "matched",
    "fileInfo": { "fileName": "张三简历.pdf", "pages": 3 },
    "cleanedText": "姓名：张三\n...",
    "extractedInfo": { "name": "张三", ... },
    "matchResults": [
      { "jobDigest": "d41d8cd98f00b204", "result": { "totalScore": 85, ... } }
    ],
    "cachedAt": 1716652800,
    "ttlSeconds": 86400
  }
}
```

---

### 6. 缓存统计

**`GET /api/cache/stats`**

请求示例：
```bash
curl http://localhost:5000/api/cache/stats
```

返回示例：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "memoryEntries": 12,
    "activeEntries": 10,
    "expiredEntries": 2,
    "parsedCount": 12,
    "extractedCount": 8,
    "matchedCount": 5,
    "estimatedMemoryBytes": 245760,
    "maxEntries": 500,
    "ttlSeconds": 86400,
    "redis": { "available": true, "keys": 12, "configured": true },
    "redisHealth": { "available": true, "url": "r-xxx.redis.rds.aliyuncs.com:6379" }
  }
}
```

---

### 7. 缓存清理

**`POST /api/cache/cleanup`**

请求示例：
```bash
curl -X POST http://localhost:5000/api/cache/cleanup
```

返回示例：
```json
{
  "code": 0,
  "msg": "清理完成，移除 2 条过期缓存",
  "data": { "removed": 2 }
}
```

---

### 完整三步骤调用流程

```bash
# Step 1: 上传简历
UPLOAD_RESP=$(curl -s -X POST http://localhost:5000/api/resume/upload -F "file=@resume.pdf")
RESUME_ID=$(echo $UPLOAD_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['resumeId'])")

# Step 2: AI 提取信息
curl -s -X POST http://localhost:5000/api/resume/extract \
  -H "Content-Type: application/json" \
  -d "{\"resumeId\": \"$RESUME_ID\"}"

# Step 3: 岗位匹配
curl -s -X POST http://localhost:5000/api/match \
  -H "Content-Type: application/json" \
  -d "{\"resumeId\": \"$RESUME_ID\", \"jobDescription\": \"高级前端工程师...\"}"
```

---

## 项目亮点与技术创新

### 架构设计

- **七层分层架构**：utils / parser / ai_service / cache / routes / exceptions + 入口层，单向依赖，高内聚低耦合
- **统一异常体系**：5 级异常类层次（AppException → ParamError / FileError / AITimeoutError / ServerError），全局 Flask errorhandler 拦截
- **统一 JSON 信封**：`{code, msg, data}` 格式，业务异常 HTTP 200 返回，前端统一处理

### AI 工程化

- **扫描版 PDF OCR 降级**：PyPDF2 提取文字为空时自动切换到 Qwen-VL 多模态模型做 OCR 识别（`_ocr_fallback()`），PyMuPDF 渲染 PDF 页面为图片 → 多模态识别 → 文本清洗，通过 `OCR_ENABLED` 环境变量控制
- **智能降级策略**：DashScope 不可用时自动切换正则提取（`_regex_fallback()`），双重降级保障系统可用性
- **多层 JSON 容错解析**：`parse_ai_json()` 支持去除 markdown 代码块 → 直接解析 → 正则提取三重容错
- **重试 + 指数退避**：最多 2 次重试，1s → 2s 退避，仅重试网络错误
- **Prompt 工程**：System Prompt 角色设定 + 严格 JSON 输出约束 + 缺失字段 null 填充

### 缓存策略

- **双层索引**：MD5（主键）+ resumeId（二级索引），O(1) 双向查询
- **惰性淘汰**：读取时检查 TTL，避免后台定时器开销
- **内存保护**：500 条上限 + 最旧优先淘汰，FC 实例内存可控
- **可选 Redis**：零配置默认内存缓存，配置 `REDIS_URL` 即启用 L2 缓存，跨 FC 实例共享

### 前端亮点

- **零依赖**：Vue 3 CDN 引入，无构建工具链，部署即用
- **SVG 环形评分图**：纯 SVG 实现四维评分可视化，CSS transition 动画
- **三步骤引导流程**：上传 → 提取 → 匹配，进度条可视化
- **API 在线状态检测**：页面加载时自动检测后端连通性

### 运维友好

- **全链路结构化日志**：Python logging 模块，统一格式 + 毫秒级计时
- **健康检查端点**：`GET /api/health` 供监控系统探活
- **CORS 预检缓存**：`Access-Control-Max-Age: 86400` 减少跨域请求
- **请求计时中间件**：每个请求自动记录方法、路径、状态码、耗时

---

## Git 提交规范

本项目采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

### 提交格式

```
<type>(<scope>): <subject>

<body>
```

### Type 类型

| type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `refactor` | 重构（非功能改动也非修复） |
| `perf` | 性能优化 |
| `style` | 代码风格调整（不影响逻辑） |
| `docs` | 文档更新 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖变更 |

### Scope 范围

| scope | 对应模块 |
|-------|---------|
| `config` | 全局配置 |
| `utils` | 工具层 |
| `parser` | PDF 解析层 |
| `ai` | AI 服务层 |
| `cache` | 缓存层 |
| `routes` | 路由层 |
| `exceptions` | 异常层 |
| `frontend` | 前端页面 |
| `app` | 应用入口 |
| `docs` | 文档 |

### 示例

```bash
feat(ai): 添加 AI 提取失败时的正则降级策略
fix(cache): 修复非重入锁导致的死锁问题
refactor(utils): 提取共享 JSON 解析器消除重复代码
docs: 完善 README 接口文档和部署说明
chore(app): 添加请求计时和 CORS 预检缓存中间件
```

---

## 项目交付清单

| 序号 | 交付项 | 说明 | 状态 |
|:----:|--------|------|:----:|
| 1 | 简历上传解析 | POST /api/resume/upload，PDF → 清洗文本 | 已完成 |
| 2 | AI 信息提取 | POST /api/resume/extract，12 字段结构化 | 已完成 |
| 3 | 岗位匹配评分 | POST /api/match，四维 0-100 评分 | 已完成 |
| 4 | 综合查询 | GET /api/resume/\<id\>，聚合全部结果 | 已完成 |
| 5 | 缓存系统 | 内存 + Redis，500 条上限，24h TTL | 已完成 |
| 6 | 缓存管理 | 统计查询 + 手动清理 + 健康检查 | 已完成 |
| 7 | 前端页面 | Vue 3 SPA，三步骤交互，SVG 评分图 | 已完成 |
| 8 | 异常处理 | 5 级错误码，全局拦截，统一格式 | 已完成 |
| 9 | AI 降级策略 | 正则兜底提取 + VL OCR 扫描版识别，环境变量控制 | 已完成 |
| 10 | 健康检查 | GET /api/health，监控探活 | 已完成 |
| 11 | CORS 支持 | 允许跨域 + 预检缓存 24h | 已完成 |
| 12 | 全链路日志 | 结构化日志 + 请求计时 | 已完成 |
| 13 | 架构文档 | ARCHITECTURE.md，含模组/接口/数据定义 | 已完成 |
| 14 | 接口文档 | README.md，含请求/返回/错误码示例 | 已完成 |
| 15 | 依赖清单 | requirements.txt，版本锁定 | 已完成 |
| 16 | 回归测试 | 10 组测试全部通过 | 已完成 |

---

## License

MIT
