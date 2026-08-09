#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全屏截图（Windows，零依赖，走 PowerShell + System.Drawing）。

用法:
  python screenshot.py [输出路径]        # 默认 ./screenshot_YYYYmmdd_HHMMSS.png
  python screenshot.py out.png

说明:
  - 只截主屏（PrimaryScreen.Bounds）
  - 截完直接喂给 recognize.py 即可闭环：截图 → 识别
"""
import datetime
import subprocess
import sys


def capture(output: str = None) -> str:
    if not output:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"screenshot_{stamp}.png"
    output = output.replace("\\", "/")
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save('{output}')
$g.Dispose(); $bmp.Dispose()
"""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
    )
    return output


if __name__ == "__main__":
    out = capture(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"截图已保存: {out}")
