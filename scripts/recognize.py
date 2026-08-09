#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qwen3.7-flash 视觉识别脚本（零依赖，纯标准库）

用法:
  python recognize.py <图片路径或URL> [更多图片...] [--prompt "问题"] [--json-only] [--max-tokens N]

路径支持通配符（如 "漫剧/*.jpeg"），会自动展开并排序；429/5xx/超时自动重试一次。

Key 配置（二选一）:
  1. 环境变量 DASHSCOPE_API_KEY=sk-xxx
  2. 文件 ~/.dashscope_key 内容为 sk-xxx
"""
import argparse
import base64
import glob
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.7-flash"
MAX_IMAGE_MB = 10  # API 对 base64 图片的大小限制

DEFAULT_PROMPT = (
    "请详细识别并描述这张图片。输出两部分：\n"
    "1) 自然语言描述：完整描述画面内容（主体/人物/动作/表情/场景/氛围/任何可见文字），中文，2-3 段。\n"
    "2) 结构化 JSON：用 ```json 代码块输出 {\"主题\":..., \"人物\":..., \"场景\":..., \"动作\":..., "
    "\"细节\":..., \"画面文字\":..., \"风格画风\":...}。\n"
    "不确定的字段写\"未知\"，不要编造。"
)

KEY_INSTRUCTIONS = """\
[错误] 未找到 API Key（DASHSCOPE_API_KEY）。
申请步骤：
  1. 打开 https://bailian.console.aliyun.com/ 注册/登录阿里云账号
  2. 页面右上角「API-KEY」→ 创建新 API-KEY（sk- 开头，模型需开通 qwen3.7-flash）
  3. 二选一配置：
     a. 设置环境变量 DASHSCOPE_API_KEY=sk-xxx
     b. 把 key 写入文件 %s
"""


def expand_paths(paths):
    """展开通配符（Windows 文件名可能含特殊字符，支持 'dir/*.jpeg' 式批量传图）。"""
    out = []
    for p in paths:
        if p.startswith(("http://", "https://")) or not glob.has_magic(p):
            out.append(p)
            continue
        matches = sorted(glob.glob(p))
        if not matches:
            raise FileNotFoundError(f"通配符未匹配到任何文件: {p}")
        out.extend(matches)
    return out


def api_call(req):
    """带一次重试的 API 调用：429/5xx/超时 时退避 2s 重试。"""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if attempt == 0 and e.code in (429, 500, 502, 503, 504):
                time.sleep(2)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 0:
                time.sleep(2)
                continue
            raise


def get_api_key():
    key = os.environ.get("DASHSCOPE_API_KEY")
    if key:
        return key.strip()
    cfg = os.path.expanduser("~/.dashscope_key")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    print(KEY_INSTRUCTIONS % cfg, file=sys.stderr)
    sys.exit(2)


def build_image_part(path):
    """本地文件 -> base64 data URI；URL -> 直接透传。"""
    if path.startswith(("http://", "https://")):
        return {"type": "image_url", "image_url": {"url": path}}
    if not os.path.isfile(path):
        raise FileNotFoundError(f"图片文件不存在: {path}")
    with open(path, "rb") as f:
        data = f.read()
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        print(f"[警告] {path} 超过 {MAX_IMAGE_MB}MB，API 可能拒绝，建议先压缩。", file=sys.stderr)
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    b64 = base64.b64encode(data).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def main():
    # Windows 中文环境默认 cp936，强制 UTF-8 避免乱码（Claude Code 按 UTF-8 读输出）
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="qwen3.7-flash 视觉识别")
    ap.add_argument("images", nargs="+", help="图片路径或 URL（可传多张）")
    ap.add_argument("--prompt", default=None, help="自定义问题（默认：详细描述+结构化 JSON）")
    ap.add_argument("--json-only", action="store_true", help="强制 JSON 结构化输出")
    ap.add_argument("--max-tokens", type=int, default=4096)
    args = ap.parse_args()

    key = get_api_key()

    try:
        images = expand_paths(args.images)
        parts = [build_image_part(p) for p in images]
    except FileNotFoundError as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)
    parts.append({"type": "text", "text": args.prompt if args.prompt else DEFAULT_PROMPT})

    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": parts}],
        "max_tokens": args.max_tokens,
    }
    if args.json_only:
        body["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        result = api_call(req)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"[错误] API 返回 {e.code}:\n{detail}", file=sys.stderr)
        if e.code == 401:
            print("API Key 无效或已过期，请重新在百炼平台创建。", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[错误] 网络请求失败: {e.reason}", file=sys.stderr)
        sys.exit(1)

    print(result["choices"][0]["message"]["content"])


if __name__ == "__main__":
    main()
