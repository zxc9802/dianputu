# 模型接入配置

本项目默认接入两个模型能力：

- 文字分析模型：`gemini-3.1-pro-preview`
- 图片生成模型：`gpt-image-2-all`

接口和默认参数见 `config/ai-models.json`。真实 API Key 不写入前端代码，运行时从环境变量读取：

- `TEXT_ANALYSIS_API_KEY`
- `IMAGE_GENERATION_API_KEY`
- `FALLBACK_IMAGE_GENERATION_API_KEY`
- `DEFAULT_IMAGE_GENERATION_OPTION_ID`，默认 `fallback`，对应 `gpt image2(2)`

文字模型默认 `max_tokens` 设置为 `4096`，避免推理模型把过小的输出额度消耗在 reasoning tokens 后导致正文为空。
图片生成默认按平台生成尺寸提交，淘宝 / 天猫等方图平台为 `2048x2048`。
