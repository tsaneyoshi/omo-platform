# -*- coding: utf-8 -*-
"""
OMO Platform - 1枚絵生成 (google-genai SDK版 / Storage対応)

記事の内容を説明するアイキャッチ画像を生成
"""

import sys
import os
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.transform.core.base import BaseTransformer
from backend.common.config import get_config
from backend.common.utils import truncate_text
from backend.common.storage import save_file
from google import genai
from google.genai import types


class ImageSingleTransformer(BaseTransformer):
    """1枚絵生成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_config = get_config()
        self.model_name = config.get("image_model", "gemini-3-pro-image-preview")
        self.style = config.get("style", "アニメ・マンガ風の高品質2Dイラスト。クリーンな線画、ソフトな陰影、鮮やかな色彩。")
        self.aspect_ratios = config.get("aspect_ratios", ["1:1"])
        # 単一設定との互換性
        if "aspect_ratio" in config:
            self.aspect_ratios = [config["aspect_ratio"]]
            
        self.image_size = config.get("image_size", "1K")
        self.reference_images_dir = config.get("reference_images_dir", None)
        self.summary_model_name = config.get("summary_model_name", "gemini-2.5-flash")
        self.max_output_tokens = config.get("max_output_tokens", 8192)
        self.prompts = config.get("prompts", {})
        
        # クライアント初期化
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        self.client = genai.Client(api_key=api_key)
    
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        記事から1枚絵を生成
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
            
            # デバッグ: 入力データを確認
            print(f"🔍 [DEBUG] Title: {title}")
            print(f"🔍 [DEBUG] Body Length: {len(body_text)}")
            print(f"🔍 [DEBUG] Body Head: {body_text[:200].replace(chr(10), ' ')}...")
            
            # 要約を生成
            print(f"📝 要約生成開始 ({self.summary_model_name}): {title[:30]}...")
            summary = self._generate_summary(title, body_text)
            print(f"📝 要約生成完了:\n{summary}")
            
            # 参照画像を読み込む
            ref_images, loaded_ref_names = self._load_reference_images()
            
            # プロンプト作成
            prompt = self._build_prompt(title, summary, loaded_ref_names)
            
            # ファイル名用のID生成 (タイトルベース)
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(" ", "_")
            if len(safe_title) > 50:
                safe_title = safe_title[:50]
            
            # contentsを準備
            contents = [prompt]
            if ref_images:
                contents.extend(ref_images)
                print(f"📎 参照画像: {len(ref_images)}枚 ({', '.join(loaded_ref_names)})")
            
            results = {}
            generated_any = False
            
            # 各アスペクト比で生成
            for aspect_ratio in self.aspect_ratios:
                print(f"🎨 画像生成開始 ({self.model_name}, {aspect_ratio}, {self.image_size}): {title[:30]}...")
                
                try:
                    # 画像生成実行 (types使用)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(
                                aspect_ratio=aspect_ratio,
                                image_size=self.image_size
                            )
                        )
                    )
                    
                    # 画像抽出
                    img_bytes = None
                    if hasattr(response, "candidates") and response.candidates:
                        for cand in response.candidates:
                            if not cand.content: continue
                            for part in cand.content.parts:
                                if part.inline_data and part.inline_data.data:
                                    img_bytes = part.inline_data.data
                                    break
                            if img_bytes: break
                    
                    if not img_bytes:
                        print(f"⚠️ 画像生成失敗 (画像なし, {aspect_ratio}): {title}")
                        continue
                    
                    # ストレージに保存
                    aspect_suffix = aspect_ratio.replace(':', 'x')
                    filename = f"images/{safe_title}_eye_catch_{aspect_suffix}.png"
                    storage_path = save_file(img_bytes, filename, "image/png")
                    
                    print(f"✅ 画像生成成功 ({aspect_ratio}): {title[:30]}... -> {storage_path}")
                    
                    # 結果に追加
                    key = f"image_path_{aspect_suffix}"
                    results[key] = storage_path
                    generated_any = True
                    
                except Exception as e:
                    print(f"⚠️ 画像生成エラー ({aspect_ratio}): {e}")
            
            if not generated_any:
                print(f"❌ すべてのアスペクト比で画像生成失敗: {title}")
                return None
            
            return {
                **results,
                "prompt": prompt,
                "mime_type": "image/png",
                "aspect_ratios": self.aspect_ratios,
                "summary": summary
            }
            
        except Exception as e:
            print(f"❌ 画像生成エラー: {article.get('title', 'unknown')} | {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_summary(self, title: str, body_text: str) -> str:
        """画像に載せるための要約を生成"""
    def _generate_summary(self, title: str, body_text: str) -> str:
        """画像に載せるための要約を生成"""
        # 設定ファイルからプロンプトを取得
        template = self.prompts.get("summary")
        
        if not template:
            print("⚠️ 要約プロンプト(summary)が設定されていません。デフォルトを使用します。")
            template = """
# 記事タイトル
{title}

# 記事本文
{body_text}

# 指示
- 記事の要点を3行程度の箇条書きで要約してください。
"""

        prompt = template.format(
            title=title,
            body_text=truncate_text(body_text, 2000)
        ).strip()
        
        # 強制力を高めるための追加指示 (これはシステム的なガードレールとして残す)
        prompt += "\n\nIMPORTANT: Output ONLY the summary text in Japanese. Do not include any thinking process, metadata, or English text."
        # デバッグ: プロンプトの先頭を確認
        print(f"🔍 [DEBUG] Prompt Head: {prompt[:200].replace(chr(10), ' ')}...")

        try:
            response = self.client.models.generate_content(
                model=self.summary_model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, # 創造性を排除し、事実に忠実に
                    max_output_tokens=self.max_output_tokens
                )
            )
            if response.text:
                text = response.text.strip()
                
                # クリーニング: 思考プロセスが混入した場合の除去
                if "SPECIAL INSTRUCTION" in text or "think:" in text:
                    print(f"⚠️ 思考プロセス混入を検知。クリーニングします。")
                    if "output:" in text:
                        parts = text.split("output:")
                        text = parts[-1].strip()
                    else:
                        lines = text.split('\n')
                        jp_lines = [line for line in lines if any(ord(c) > 128 for c in line)]
                        if jp_lines:
                            text = "\n".join(jp_lines)
                
                return text
            else:
                print("⚠️ 要約生成: レスポンスが空です (safety block?)")
                return truncate_text(body_text, 100, suffix="...")
        except Exception as e:
            print(f"⚠️ 要約生成失敗: {e}")
            # 失敗時は本文の冒頭を使用
            return truncate_text(body_text, 100, suffix="...")

    def _load_reference_images(self) -> Tuple[List[Image.Image], List[str]]:
        """参照画像を読み込む"""
        if not self.reference_images_dir:
            return [], []
        
        # プロジェクトルートからの相対パス (backend/transform/image/single.py から見て)
        # 実行時のカレントディレクトリ(プロジェクトルート)を基準にするのが安全
        ref_dir = Path(os.getcwd()) / self.reference_images_dir
        
        if not ref_dir.exists():
            print(f"ℹ️ 参照画像フォルダが見つかりません: {ref_dir}")
            return [], []
        
        ref_images = []
        loaded_names = []
        
        # logo.png と mascot.png を探す
        for img_name in ["logo.png", "mascot.png"]:
            img_path = ref_dir / img_name
            if img_path.exists():
                try:
                    img = Image.open(img_path)
                    ref_images.append(img)
                    loaded_names.append(img_name)
                    print(f"📎 参照画像読み込み: {img_name}")
                except Exception as e:
                    print(f"⚠️ 参照画像読み込み失敗: {img_name} | {e}")
            else:
                print(f"ℹ️ 参照画像なし: {img_name} (スキップ)")
        
        return ref_images, loaded_names
            
    def _build_prompt(self, title: str, summary: str, loaded_ref_names: List[str]) -> str:
        """プロンプトを作成"""
        ref_instruction = ""
        if loaded_ref_names:
            instructions = []
            instructions.append("# 参照画像の配置")
            instructions.append("- 添付した参照画像を以下のように配置してください:")
            
            if "logo.png" in loaded_ref_names:
                instructions.append("  - ロゴ(logo.png): 画像の左上隅に小さく配置してください")
            if "mascot.png" in loaded_ref_names:
                instructions.append("  - ゆるキャラ(mascot.png): 画像の右下または適切な位置に親しみやすく配置してください")
            
            instructions.append("- **重要**: 参照画像（ロゴ、キャラクター）は、提供された画像を**そのまま**使用してください。")
            instructions.append("- 色、形状、デザインの改変、デフォルメ、描き直しは**一切禁止**です。")
            instructions.append("- 提供された画像データをそのままレイアウトに配置するイメージで生成してください。")
            instructions.append("- 参照画像は本文の邪魔にならないよう、適度なサイズで配置してください")
            
            ref_instruction = "\n".join(instructions)

        template = self.prompts.get("image_generation", """
以下の記事の内容を伝える、文字入りのアイキャッチ画像（スライド資料風）を生成してください。

# 記事タイトル
{title}

# 掲載する情報
{summary}

# デザイン指示
- 記事のタイトル「{title}」を画像の上部に大きく配置してください。
- タイトルの下に、上記の「掲載する情報」を配置してください。情報は整理して見やすくレイアウトしてください。
- すべての文字は日本語で、視認性の高い太めのフォントを使用してください。誤字脱字がないように注意してください。
- 背景はシンプルでクリーンなデザインにし、文字の可読性を最優先してください。イラスト要素は控えめにしてください。
- 文字が背景に埋もれないよう、文字の縁取りや背景ボックス、明度調整を行ってください。
- 全体として、市民に必要な情報がしっかりと伝わる、プロフェッショナルなスライド資料のようなデザインにしてください。
- {style}
{ref_instruction}
""")

        return template.format(
            title=title,
            summary=summary,
            style=self.style,
            ref_instruction=ref_instruction
        ).strip()
