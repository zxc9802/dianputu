# 账号级保存风格设计

## 背景

Gemini 规划自定义风格或分析图片对标后，前端会把结果保存为当前项目的 `customStyle`。这个风格目前只能随当前项目草稿或历史记录一起存在，用户无法把一个满意的风格单独保存为可复用资产。

本功能新增账号级“我的保存风格”。用户可以把当前 Gemini 风格保存到账户下，之后在任意新项目中选择复用，也可以删除已保存风格。删除只影响风格库副本，不影响当前项目里已经选中的风格对象。

## 目标

- 用户在风格页看到当前 Gemini 风格后，可以保存到自己的账号风格库。
- 保存时默认使用 Gemini 返回的风格名，用户可改名。
- 用户可以在风格页查看账号下已保存风格，并一键选择为当前 `customStyle`。
- 用户可以删除账号下的保存风格。
- 后端所有保存、列表、删除操作按当前 SSO 用户 `user_id` 隔离。
- 已保存风格沿用现有 `StyleOption` 结构，生成链路继续使用当前 `customStyle` 逻辑。

## 非目标

- 不做公开共享风格库。
- 不做跨账号授权、团队共享或管理员管理。
- 不把保存风格混入“项目模板”。模板仍表示模块、平台、品类和固定风格选择。
- 不在删除保存风格时回滚或清空当前工作区的 `customStyle`。

## 后端设计

新增 `saved_styles` 表：

- `id TEXT PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `user_snapshot_json TEXT NOT NULL DEFAULT '{}'`
- `name TEXT NOT NULL DEFAULT ''`
- `style_json TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

新增索引：

- `idx_saved_styles_user_created` on `(user_id, created_at DESC)`

新增数据库 helper：

- `list_saved_styles(user_id, limit=50, offset=0)`
- `save_style(user_id, user_snapshot, record)`
- `delete_saved_style(user_id, style_id)`

新增 FastAPI router `backend/app/routers/styles.py`，挂载在 `/api/styles`：

- `GET /api/styles/saved`
  - 返回当前用户保存的风格列表。
  - 响应包含 `id`、`name`、`style`、`created_at`、`updated_at`。
- `POST /api/styles/saved`
  - 请求包含 `name` 和 `style`。
  - 后端把 `name` 写入返回给前端的 `style.name`，其余风格字段保留。
  - 如果没有传 `id`，生成新 id；如果传了 id，只允许更新当前用户自己的记录。
- `DELETE /api/styles/saved/{style_id}`
  - 只删除当前用户自己的记录。
  - 找不到或数据库未配置时返回 404。

数据库未配置时，账号级风格库返回服务不可用，不使用浏览器本地兜底，避免用户误以为已账号级同步。

## 前端设计

新增类型：

- `SavedStyleRecord`
  - `id`
  - `name`
  - `style: StyleOption`
  - `created_at`
  - `updated_at`

新增 API helper：

- `fetchSavedStyles()`
- `saveSavedStyle(style, name)`
- `deleteSavedStyle(id)`

页面状态新增：

- `savedStyles`
- `isLoadingSavedStyles`
- `isSavingStyle`
- `deletingSavedStyleId`

加载默认配置后并行读取账号风格库。保存成功后把新记录插到列表顶部。删除成功后从列表中移除。

`StyleStep` 新增 props：

- `savedStyles`
- `isLoadingSavedStyles`
- `isSavingStyle`
- `deletingSavedStyleId`
- `onSaveCustomStyle`
- `onSelectSavedStyle`
- `onDeleteSavedStyle`

风格页交互：

- 当前 `customStyle` 存在时，在 AI 自定义风格卡内显示“保存到我的风格”按钮。
- 点击后弹窗让用户确认或改名，默认值为 `customStyle.name`。
- 风格页新增“我的保存风格”区，渲染账号下已保存风格。
- 每个保存风格卡支持“使用”和删除按钮。
- 使用保存风格时，前端把记录里的 `style` 复制到 `customStyle`，设置 `styleSource` 为 `ai_custom`，状态提示“已使用保存风格：xxx”。
- 删除保存风格不会修改当前 `customStyle` 或 `styleSource`。

## 数据流

1. 用户点击 Gemini 规划或图片对标分析。
2. 后端返回 `StyleOption`，前端写入 `customStyle`。
3. 用户点击“保存到我的风格”，输入或确认名称。
4. 前端调用 `POST /api/styles/saved`。
5. 后端用当前 SSO `user_id` 保存 `style_json`。
6. 用户以后进入风格页时，前端调用 `GET /api/styles/saved` 展示风格库。
7. 用户选择保存风格后，生成链路继续发送 `custom_style` 给现有 `/api/projects/generate/jobs`。

## 错误处理

- 保存时没有 `customStyle`：前端提示先规划或分析风格。
- 用户取消命名弹窗：不发请求。
- API 失败：状态栏提示“保存风格失败”或“删除风格失败”。
- 删除失败：保留本地列表，不做乐观删除。
- 列表读取失败：展示空列表并提示“保存风格暂不可用”。

## 测试

后端：

- `ensure_tables` 创建 `saved_styles` 表和用户索引。
- `list_saved_styles` 必须按 `user_id` 过滤。
- `save_style` 必须写入 `user_id` 和 `user_snapshot_json`，并只允许同用户更新。
- `delete_saved_style` 必须按 `user_id` 和 `id` 删除。
- router 依赖 `require_app_user`，不会暴露跨用户数据。

前端：

- 静态契约测试确认风格页有“保存到我的风格”“我的保存风格”“删除”入口。
- API 测试确认新增 helper 调用 `/api/styles/saved`。
- 项目草稿不保存整份 `savedStyles`，避免账号风格库被写进当前项目 state。

## 自查

- 无占位需求或未定字段。
- 保存、选择、删除的语义互不冲突。
- 账号级存储明确依赖 SSO `user_id`。
- 生成链路不新增分支，继续复用现有 `customStyle`。
- 范围聚焦于风格库，不扩展到模板、团队共享或历史记录。
