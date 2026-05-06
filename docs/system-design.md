# 商品详情图生成智能体系统设计

## 目标

实现 PRD 中的 V1 MVP：上传资料、选择品类和风格、AI 提炼信息、人工确认、选择 7 个固定模块、生成详情图、预览并导出。

## 架构

- `frontend/`：Next.js 15 + TypeScript，承载向导式 UI。
- `backend/`：FastAPI，承载项目状态、模型配置、文字分析、生图任务和导出接口。
- `config/ai-models.json`：保存非密钥模型配置。
- `.env.local` 或部署环境变量：保存真实 API Key。

前端不直接访问外部模型 API，也不持有 API Key。所有模型调用统一走后端服务。

## 模型

- 文字分析模型：`gemini-3.1-pro-preview`
- 默认输出额度：`max_tokens = 4096`
- 图片生成模型：`gpt-image-2-all`
- 默认图片尺寸：`1024x1024`

## MVP 范围

第一版先做内部可用闭环：

1. 项目创建使用本地演示数据。
2. 上传文件 UI 先完成交互与状态，不强依赖真实存储。
3. AI 提炼可调用文字模型；无 key 时返回演示数据。
4. 图片生成可调用生图模型；无 key 时返回演示图占位。
5. 导出先返回生成结果 URL 列表，长图拼接后续接入 Pillow。

## 安全边界

- 不把 API Key 写进前端源码。
- 不把 API Key 写入 `config/ai-models.json`。
- `.env*` 默认被 `.gitignore` 排除，`.env.example` 例外。
