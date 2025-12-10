# -*- coding: utf-8 -*-
"""
OMO Platform - わかりやすいテキスト生成

行政文書を市民にわかりやすい言葉に変換
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


class EasyTextTransformer(BaseTransformer):
    """わかりやすいテキスト生成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.llm = get_llm_client()
        # max_chars は使用しないが、設定ファイルに残っていてもエラーにならないようにgetしておく
        self.max_output_tokens = config.get("max_output_tokens", 8192)
        self.prompts = config.get("prompts", {})
    
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        記事をわかりやすいテキストに変換
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
            
            # 本文が長すぎる場合は切り詰め（入力トークン制限対策）
            body_preview = truncate_text(body_text, 3000, suffix="...")
            
            # プロンプト作成
            # ここでは「簡潔テキスト」ではなく「本文」を元にする
            prompt = self._build_prompt(title, body_preview)
            
            # Gemini APIでテキスト生成
            response = self.llm.generate(
                prompt=prompt,
                generation_config=self.llm.get_json_config(max_tokens=self.max_output_tokens),
                retry=3
            )
            
            # テキスト抽出
            easy_text = self.llm.extract_text(response)
            
            if not easy_text:
                print(f"⚠️ わかりやすいテキスト生成失敗 (空レスポンス): {title}")
                return self._create_fallback(title, body_text)
            
            # クリーニング
            easy_text = easy_text.strip()
            
            # 文字数制限による切り詰めは行わない
            
            # ファイル保存
            storage_path = None
            try:
                safe_title = re.sub(r'[\\/*?:\"<>|]', "", title).replace(" ", "_")
                if len(safe_title) > 50:
                    safe_title = safe_title[:50]
                
                filename = f"texts/{safe_title}_easy.txt"
                storage_path = save_file(easy_text.encode('utf-8'), filename, "text/plain")
                print(f"💾 テキスト保存: {storage_path}")
            except Exception as e:
                print(f"⚠️ テキスト保存失敗: {e}")
            
            print(f"✅ わかりやすいテキスト生成: {title[:30]}... ({len(easy_text)}文字)")
            
            return {
                "content": easy_text,
                "length": len(easy_text),
                "storage_path": storage_path
            }
            
        except Exception as e:
            print(f"❌ わかりやすいテキスト生成エラー: {article.get('title', 'unknown')} | {e}")
            return self._create_fallback(article.get("title", ""), article.get("body_text", ""))
    
    def _build_prompt(self, title: str, body_text: str) -> str:
        """プロンプトを作成"""
        template = self.prompts.get("easy_text")
        
        # デバッグ: テンプレートの確認
        if not template:
            print("⚠️ [DEBUG] easy_text template NOT found in config")
        else:
            print(f"🔍 [DEBUG] easy_text template found (len={len(template)})")
        
        if not template:
            # デフォルト
            return f"""以下の行政文書の要約を、市民にとってわかりやすい言葉に言い換えてください。

# 記事タイトル
{title}

# 元の本文 (参考)
{body_text}

# 指示
- 専門用語や行政用語を平易な言葉に置き換えてください
- 難しい漢字や表現は、ひらがなや簡単な言葉に変えてください
- 「です・ます」調で親しみやすく書いてください
- 重要な情報（日時、場所、対象者など）は必ず残してください
- 箇条書き形式でもOKです

# 出力形式
わかりやすく言い換えたテキストのみを出力してください。説明や前置きは不要です。
"""
        
        return template.format(
            title=title,
            body_text=body_text
        )
    
    def _create_fallback(self, title: str, body_text: str) -> Dict[str, Any]:
        """
        フォールバック: 本文の先頭を使用
        """
        # タイトル + 本文
        fallback = f"{title}\n{body_text}"
        
        print(f"⚠️ フォールバック使用: {title[:30]}...")
        
        return {
            "content": fallback,
            "length": len(fallback),
            "is_fallback": True
        }
