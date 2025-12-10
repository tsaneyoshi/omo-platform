# -*- coding: utf-8 -*-
"""
OMO Platform - 簡潔テキスト生成

長い記事を3行程度の簡潔なテキストに要約
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import re

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.transform.core.base import BaseTransformer
from backend.common.llm import get_llm_client
from backend.common.utils import truncate_text
from backend.common.storage import save_file


class SimpleTextTransformer(BaseTransformer):
    """簡潔テキスト生成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.llm = get_llm_client()
        self.max_chars = config.get("max_chars", 150)
        self.max_output_tokens = config.get("max_output_tokens", 8192)
        self.prompts = config.get("prompts", {})
    
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        記事を簡潔なテキストに変換
        """
        if not self.is_enabled():
            return None
        
        if not self.validate_article(article):
            print(f"⚠️ 記事データが不正: {article.get('title', 'unknown')}")
            return None
        
        try:
            # 入力データを準備
            title = article.get("title", "")
            body_text = article.get("body_text", "")
            
            # 本文が長すぎる場合は切り詰め
            body_preview = truncate_text(body_text, 1500, suffix="...")
            
            # プロンプト作成
            prompt = self._build_prompt(title, body_preview)
            
            # Gemini APIで要約生成
            response = self.llm.generate(
                prompt=prompt,
                generation_config=self.llm.get_json_config(max_tokens=self.max_output_tokens),
                retry=3
            )
            
            # テキスト抽出
            raw_text = self.llm.extract_text(response)
            
            if not raw_text:
                print(f"⚠️ 要約生成失敗 (空レスポンス): {title}")
                return self._create_fallback(title, body_text)
            
            # 簡潔テキストを抽出
            simple_text = self._extract_simple_text(raw_text)
            
            # 文字数チェック
            if len(simple_text) > self.max_chars:
                simple_text = truncate_text(simple_text, self.max_chars, suffix="…")
            
            # ファイル保存
            storage_path = None
            try:
                safe_title = re.sub(r'[\\/*?:\"<>|]', "", title).replace(" ", "_")
                if len(safe_title) > 50:
                    safe_title = safe_title[:50]
                
                filename = f"texts/{safe_title}_simple.txt"
                storage_path = save_file(simple_text.encode('utf-8'), filename, "text/plain")
                print(f"💾 テキスト保存: {storage_path}")
            except Exception as e:
                print(f"⚠️ テキスト保存失敗: {e}")
            
            print(f"✅ 簡潔テキスト生成: {title[:30]}... ({len(simple_text)}文字)")
            
            return {
                "content": simple_text,
                "length": len(simple_text),
                "storage_path": storage_path
            }
            
        except Exception as e:
            print(f"❌ 簡潔テキスト生成エラー: {article.get('title', 'unknown')} | {e}")
            return self._create_fallback(article.get("title", ""), article.get("body_text", ""))
    
    def _build_prompt(self, title: str, body_text: str) -> str:
        """
        プロンプトを作成
        """
        template = self.prompts.get("simple_text")
        
        # デバッグ: テンプレートの確認
        if not template:
            print("⚠️ [DEBUG] simple_text template NOT found in config")
        else:
            print(f"🔍 [DEBUG] simple_text template found (len={len(template)})")
        
        if not template:
            # デフォルト（設定ファイルがない場合のフォールバック）
            return f"""以下の記事を、市民にわかりやすく簡潔に要約してください。

# 要件
- 3行以内、{self.max_chars}文字以内
- 箇条書き形式でもOK
- 重要な情報（対象者、期限、場所など）を優先
- 専門用語は避け、平易な言葉で
- 「です・ます」調

# 記事タイトル
{title}

# 記事本文
{body_text}

# 出力形式
簡潔な要約のみを出力してください。説明や前置きは不要です。
"""
        
        return template.format(
            title=title,
            body_text=body_text,
            max_chars=self.max_chars
        )
    
    def _extract_simple_text(self, raw_text: str) -> str:
        """
        生成されたテキストから簡潔テキストを抽出
        """
        # 余分な説明を除去
        text = raw_text.strip()
        
        # 「以下のように要約できます」などの前置きを除去
        lines = text.split("\n")
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 前置き的な行をスキップ
            if any(skip in line for skip in ["要約", "まとめ", "以下", "次のとおり"]):
                if len(line) < 30:  # 短い前置きのみスキップ
                    continue
            
            clean_lines.append(line)
        
        return "\n".join(clean_lines)
    
    def _create_fallback(self, title: str, body_text: str) -> Dict[str, Any]:
        """
        フォールバック: 本文の先頭を使用
        """
        # タイトル + 本文の先頭
        fallback = f"{title}\n{body_text[:100]}…"
        fallback = truncate_text(fallback, self.max_chars, suffix="…")
        
        print(f"⚠️ フォールバック使用: {title[:30]}...")
        
        return {
            "content": fallback,
            "length": len(fallback),
            "is_fallback": True
        }
