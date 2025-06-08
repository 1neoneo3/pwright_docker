#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
playwright-stealthのpkg_resources依存を修正するスクリプト
importlib.resourcesを使用するように変更します
"""

import os
import sys
import shutil
from pathlib import Path

def main():
    # 仮想環境のパスを取得
    venv_path = Path('.venv/lib/python3.11/site-packages/playwright_stealth')
    
    # stealth.pyのパス
    stealth_path = venv_path / 'stealth.py'
    
    # バックアップを作成
    backup_path = venv_path / 'stealth.py.bak'
    shutil.copy2(stealth_path, backup_path)
    print(f"バックアップを作成しました: {backup_path}")
    
    # ファイルを読み込む
    with open(stealth_path, 'r') as f:
        content = f.read()
    
    # pkg_resourcesをimportlib.resourcesに置き換え
    content = content.replace(
        'import pkg_resources',
        'import importlib.resources as pkg_resources'
    )
    
    # from_file関数を修正
    content = content.replace(
        "return pkg_resources.resource_string('playwright_stealth', f'js/{name}').decode()",
        "return pkg_resources.read_text('playwright_stealth.js', name)"
    )
    
    # 修正したファイルを書き込む
    with open(stealth_path, 'w') as f:
        f.write(content)
    
    print(f"playwright-stealthのソースコードを修正しました: {stealth_path}")
    print("importlib.resourcesを使用するように変更しました")

if __name__ == "__main__":
    main()
