---
name: vision-recognize
description: |
  当用户发来图片（本地路径、URL、粘贴截图）并要求识别/描述/解读图片内容时，必须激活本 skill：
  "你能看到这张图吗"、"这张图是什么"、"帮我看看这张图"、"图片里有什么"、"识别这张图"、
  "这张图讲了什么"、"图里的人在干嘛"、"看看这张图上的字"、"这是什么画风" 等场景。
  尤其当当前会话模型不支持图片输入、Claude 自己看不到图时，识别工作必须交给本 skill。

  实现方式：调用 qwen3.7-flash（阿里云百炼 DashScope OpenAI 兼容 API）视觉模型，
  把图片转 base64 发送，返回中文自然语言描述 + 结构化 JSON（主题/人物/场景/动作/细节/画面文字/风格）。
  支持多图批量识别、URL 图片、自定义提问（OCR 文字、表情分析、画风判断等）。

  不适用：图片编辑/裁剪/格式转换/压缩（纯操作不需要 AI 理解）；视频识别（仅静态图片）。
metadata:
  model: qwen3.7-flash
  api_endpoint: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
  price: 输入 ¥0.2 / 输出 ¥0.8 每百万 token（2026-08）
  key_source: https://bailian.console.aliyun.com/
---

# 视觉识别（qwen3.7-flash）

当前会话的模型可能看不到图片。本 skill 借 qwen3.7-flash 视觉模型完成图片理解：
本地图片转 base64 发给 API，返回自然语言描述 + 结构化 JSON。

## 什么时候用

- 用户给出图片路径 / URL / 截图，要求描述、识别、解读、或针对画面提问
- 用户问"你能看到这张图吗" —— 能读到图片文件不等于看懂内容，识别交给本 skill
- 批量识别：一次传多张图路径
- 特定问题：画面文字 OCR、"这是哪个角色"、"什么表情"、"什么画风" → 把用户问题作为 prompt

## 工作流程

1. **确认图片**：本地路径先验证存在；URL 直接可用
2. **调用识别脚本**（位于本 skill 目录 `scripts/recognize.py`，通常完整路径
   `~/.claude/skills/vision-recognize/scripts/recognize.py`，需要 Python 3，无第三方依赖）：

   ```bash
   python ~/.claude/skills/vision-recognize/scripts/recognize.py <图片路径或URL> [更多图片...]
   ```

3. **展示结果**：先呈现自然语言描述，再展示 JSON 块。用户只要其一就按需裁剪。
4. **key 缺失时**：脚本会输出申请指引（bailian.console.aliyun.com 创建 API-KEY），
   原样转述给用户，不要自己瞎编图片内容。

## 主动截图看屏幕

当用户想让我"看看屏幕/界面/报错窗口"（而不是提供图片文件）时，先截图再识别，两步闭环：

```bash
python ~/.claude/skills/vision-recognize/scripts/screenshot.py /tmp/screen.png
python ~/.claude/skills/vision-recognize/scripts/recognize.py /tmp/screen.png --prompt "这是什么界面？有什么问题？"
```

注意：截屏包含用户屏幕上的一切内容（可能含敏感信息），识别后只概括描述，不逐字复述密码/聊天等敏感内容。
网页内容优先用 Playwright MCP 的 `browser_take_screenshot` 截特定页面，比全屏更精准。

## 自定义提问

用户有具体问题（而不是"描述一下"）时，把问题作为 prompt 传入：

```bash
python ~/.claude/skills/vision-recognize/scripts/recognize.py 图片路径 --prompt "图里的人是什么表情？"
```

## 注意事项

- 单图建议 ≤10MB（API 限制），超限脚本会警告；大图先压缩再识别
- 路径支持通配符（文件名可能含特殊字符，如 `漫剧/Anime_male_protagonist_kneeling*202607211620.jpeg`），
  传 `--prompt` 时问题会被追加为文本部分，图片在前
- 默认输出 = 自然语言 + JSON 双格式；只要 JSON 加 `--json-only`
- 网络抖动自动重试一次（429/5xx/超时），仍失败就把报错原样给用户
- key 配置二选一：环境变量 `DASHSCOPE_API_KEY`，或文件 `~/.dashscope_key`
- 识别失败（网络/鉴权/超时）时，把脚本的报错信息给用户，不要假装成功
