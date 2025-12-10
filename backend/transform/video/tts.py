# -*- coding: utf-8 -*-
"""
OMO Platform - TTS (Gemini)

Gemini TTSでテキストを音声化
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from google import genai
from google.genai import types


class GeminiTTS:
    """Gemini TTS"""
    
    def __init__(self, model: str = "gemini-2.5-flash-preview-tts", voice: str = "Autonoe", style: str = "日本語で読み上げてください。", pronunciation_dict: Optional[Dict[str, str]] = None):
        """
        Args:
            model: TTSモデル名
            voice: 音声名
            style: スタイル指示
            pronunciation_dict: 発音辞書 {元の表記: 読み仮名}
        """
        self.model = model
        self.voice = voice
        self.style = style
        self.pronunciation_dict = pronunciation_dict or {}
        
        # クライアント初期化
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        self.client = genai.Client(api_key=api_key)
    
    def _apply_pronunciation(self, text: str) -> str:
        """発音辞書を適用"""
        result = text
        for original, reading in self.pronunciation_dict.items():
            result = result.replace(original, reading)
        return result
    
    def generate(self, text: str, output_path: str, retries: int = 3) -> bool:
        """
        テキストを音声化してMP3として保存
        
        Args:
            text: 読み上げるテキスト
            output_path: 出力MP3ファイルパス
            retries: リトライ回数
        
        Returns:
            成功したらTrue
        """
        if not text:
            print("⚠️ テキストが空です")
            return False
        
        # 発音辞書を適用
        text = self._apply_pronunciation(text)
        
        print(f"🔊 Gemini TTS: model={self.model}, voice={self.voice}")
        
        # プロンプト作成
        prompt = self._build_prompt(text)
        
        for attempt in range(retries):
            try:
                # TTS実行
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=self.voice
                                )
                            )
                        )
                    )
                )
                
                # 音声データを抽出（Raw PCM）
                pcm_data = self._extract_audio(response)
                
                if not pcm_data:
                    raise ValueError("音声データが見つかりません")
                
                # PCMを一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp_pcm:
                    tmp_pcm.write(pcm_data)
                    pcm_path = tmp_pcm.name
                
                try:
                    # FFmpegでPCM → MP3変換
                    self._convert_pcm_to_mp3(pcm_path, output_path)
                    print(f"✅ TTS保存: {output_path}")
                    return True
                finally:
                    # 一時PCMファイル削除
                    if os.path.exists(pcm_path):
                        os.remove(pcm_path)
                
            except Exception as e:
                print(f"⚠️ TTS失敗 (試行 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(1.0)
                else:
                    print(f"❌ TTS失敗: {e}")
                    return False
        
        return False
    
    def _build_prompt(self, text: str) -> str:
        """プロンプト作成"""
        if self.style:
            return f"{self.style}\n\n{text}"
        return text
    
    def _extract_audio(self, response) -> Optional[bytes]:
        """レスポンスから音声データを抽出"""
        # candidates経由
        if hasattr(response, "candidates") and response.candidates:
            for cand in response.candidates:
                if not cand.content: continue
                for part in cand.content.parts:
                    if part.inline_data and part.inline_data.data:
                        return part.inline_data.data
        
        # parts直接
        if hasattr(response, "parts"):
            for part in response.parts:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
        
        return None
    
    def _convert_pcm_to_mp3(self, pcm_path: str, mp3_path: str):
        """PCMをMP3に変換"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "s16le",      # 16-bit signed little-endian PCM
            "-ar", "24000",     # サンプリングレート 24kHz
            "-ac", "1",         # モノラル
            "-i", pcm_path,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            mp3_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg変換失敗: {result.stderr}")
