# -*- coding: utf-8 -*-
"""
OMO Platform - Gemini画像生成

Gemini APIで画像を生成
"""

import os
import time
from typing import Optional, Dict, Any
from google import genai
from google.genai import types


class GeminiImageGenerator:
    """Gemini画像生成"""
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        """
        Args:
            model: モデル名
        """
        self.model = model
        
        # クライアント初期化
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        self.client = genai.Client(api_key=api_key)
    
    def generate(self, prompt: str, output_path: str, aspect_ratio: str = "1:1", reference_images: Optional[Dict[str, Any]] = None, image_size: str = "1K") -> bool:
        """
        画像を生成して保存
        
        Args:
            prompt: プロンプト
            output_path: 保存先パス
            aspect_ratio: アスペクト比 ("1:1", "16:9", "9:16" など)
            reference_images: 参照画像の辞書 {filename: PIL.Image}
            image_size: 画像サイズ ("1K", "2K", "4K")
        
        Returns:
            成功したらTrue
        """
        if not prompt:
            print("⚠️ プロンプトが空です")
            return False
        
        print(f"🎨 画像生成 ({self.model}): {prompt[:50]}... (Ratio: {aspect_ratio}, Size: {image_size})")
        
        try:
            # コンテンツ構築 (プロンプト + 参照画像)
            contents = [prompt]
            if reference_images:
                for name, img in reference_images.items():
                    contents.append(img)
                    # print(f"   + Ref: {name}")

            # 設定
            conf = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size
                )
            )
            
            # 画像生成
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=conf
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
            
            # 画像データを保存
            if img_bytes:
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
                print(f"✅ 画像保存: {output_path}")
                return True
            else:
                print("⚠️ 画像が生成されませんでした")
                return False
                
        except Exception as e:
            print(f"❌ 画像生成失敗: {e}")
            return False
