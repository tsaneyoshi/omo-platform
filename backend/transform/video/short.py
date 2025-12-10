# -*- coding: utf-8 -*-
"""
OMO Platform - ショート動画生成 (完全版・強化版)

text_script の台本 → ビートごとに画像生成 → 動画
TTS失敗時は無音でフォールバック
"""

import sys
import os
import shutil
import hashlib
import tempfile
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.transform.core.base import BaseTransformer
from backend.common.storage import save_file
from backend.transform.video.tts import GeminiTTS
from backend.transform.video.image_gen import GeminiImageGenerator
from backend.transform.video.compositor import VideoCompositor


# デフォルトの解像度マッピング（設定がない場合のフォールバック）
DEFAULT_ASPECT_RATIO_SIZES = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

# シーン長の制限
MIN_SCENE_SEC = 3.0
MAX_SCENE_SEC = 20.0

# 動画の最後の余韻(秒) - 各シーンの末尾とBGM合成時の余韻
TAIL_SEC = 0.6


class VideoShortTransformer(BaseTransformer):
    """ショート動画生成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.aspect_ratios = config.get("aspect_ratios", ["1:1"])
        self.fps = config.get("fps", 30)
        self.duration_max = config.get("duration_max", 60)
        self.generate_images = config.get("generate_images", False)  # 画像生成フラグ
        
        # TTS設定
        tts_config = config.get("tts", {})
        self.tts = GeminiTTS(
            model=tts_config.get("model", "gemini-2.5-flash-preview-tts"),
            voice=tts_config.get("voice", "Autonoe"),
            style=tts_config.get("style", "日本語で読み上げてください。"),
            pronunciation_dict=tts_config.get("pronunciation_dict", {})
        )
        
        # 画像生成設定
        self.image_gen = GeminiImageGenerator(
            model=config.get("image_model", "gemini-2.5-flash")
        )
        
        # テロップ設定
        self.telop_config = config.get("telop", {})
        
        # BGM設定
        self.bgm_config = config.get("bgm", {})
        
        # 参照画像ディレクトリ
        self.reference_images_dir = config.get("reference_images_dir", "assets/video")
        self.image_size = config.get("image_size", "1K")
        
        # 余韻設定
        self.tail_sec = float(config.get("tail_sec", TAIL_SEC))
        
        # 解像度設定を読み込み
        resolution_config = config.get("resolution", {})
        self.aspect_ratio_sizes = {}
        for ratio, size in resolution_config.items():
            if isinstance(size, list) and len(size) == 2:
                self.aspect_ratio_sizes[ratio] = tuple(size)
        
        # フォールバック: 設定がない場合はデフォルトを使用
        if not self.aspect_ratio_sizes:
            self.aspect_ratio_sizes = DEFAULT_ASPECT_RATIO_SIZES
        
        print(f"✨ VideoShortTransformer初期化: aspect_ratios={self.aspect_ratios}, resolutions={self.aspect_ratio_sizes}, tail_sec={self.tail_sec}")
        self.reference_images = {}

    def _load_reference_images(self) -> Dict[str, Image.Image]:
        """参照画像を読み込む"""
        images = {}
        if not self.reference_images_dir:
            return images
            
        ref_dir = Path(self.reference_images_dir)
        if not ref_dir.exists():
            # プロジェクトルートからの相対パスとして試す (簡易)
            # PYTHONPATHが通っている前提で、カレントディレクトリ基準で探す
            pass

        if ref_dir.exists() and ref_dir.is_dir():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                for img_path in ref_dir.glob(ext):
                    try:
                        img = Image.open(img_path)
                        images[img_path.name] = img
                        print(f"🖼️ 参照画像ロード: {img_path.name}")
                    except Exception as e:
                        print(f"⚠️ 参照画像ロード失敗 ({img_path.name}): {e}")
        return images
    
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        記事から動画を生成
        """
        if not self.is_enabled():
            return None
        
        if not self.validate_article(article):
            print(f"⚠️ 記事データが不正: {article.get('title', 'unknown')}")
            return None
        
        try:
            # 参照画像ロード
            self.reference_images = self._load_reference_images()
            
            # 必要なデータを取得
            title = article.get("title", "")
            transformed_content = article.get("transformedContent", {})
            
            # 台本を取得
            script_data = transformed_content.get("text_script", {})
            
            if not script_data or not script_data.get("beats"):
                print(f"⚠️ 台本が見つかりません: {title}")
                return None
            
            beats = script_data.get("beats", [])
            script_title = script_data.get("title", title)
            
            print(f"🎬 動画生成開始 (台本使用): {title[:30]}... ({len(beats)}シーン)")
            print(f"   画像生成: {'ON' if self.generate_images else 'OFF (プレースホルダー)'} (model={self.image_gen.model})")
            
            # ファイル名用のID生成 (タイトルベース)
            # タイトルからファイル名に使えない文字を除去
            safe_title = re.sub(r'[\\/*?:"<>|]', "", script_title).replace(" ", "_")
            # 長すぎる場合は切り詰める
            if len(safe_title) > 50:
                safe_title = safe_title[:50]
            
            file_base_name = safe_title
            
            # 一時ディレクトリ
            with tempfile.TemporaryDirectory() as tmpdir:
                # 各シーンの素材を生成 (音声 + 画像)
                scene_assets = []
                
                for i, beat in enumerate(beats, 1):
                    text = beat.get("text", "") or beat.get("narration", "")
                    image_prompt = beat.get("imagePrompt", "") or beat.get("visual_prompt", "")
                    
                    if not text:
                        continue
                    
                    # 1. 音声生成
                    audio_path = os.path.join(tmpdir, f"scene_{i}.mp3")
                    telop_text = beat.get("telop", "")
                    print(f"🔊 シーン{i}/{len(beats)}")
                    print(f"   ナレーション: {text}")
                    print(f"   テロップ: {telop_text}")
                    
                    success = False
                    try:
                        success = self.tts.generate(text, audio_path)
                    except Exception as e:
                        print(f"⚠️ TTS例外 (シーン{i}): {e}")
                    
                    # 失敗または0バイトなら無音フォールバック
                    if not success or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                        print(f"⚠️ TTS失敗 -> 無音フォールバック (シーン{i})")
                        duration = self._safe_len_seconds(text)
                        self._generate_silent_mp3(audio_path, duration)
                    else:
                        # デバッグ: ファイルヘッダー確認
                        try:
                            with open(audio_path, "rb") as f:
                                head = f.read(8)
                                hex_head = " ".join(f"{b:02X}" for b in head)
                                print(f"   [DEBUG] Audio File Header: {hex_head} (Size: {os.path.getsize(audio_path)})")
                        except Exception:
                            pass
                    
                    # 推定時間を計算 (ffprobe失敗時のバックアップ用)
                    estimated_duration = self._safe_len_seconds(text)
                    
                    scene_assets.append({
                        "scene_id": i,
                        "text": text,
                        "image_prompt": image_prompt,
                        "audio_path": audio_path,
                        "telop": beat.get("telop", text[:40]),
                        "estimated_duration": estimated_duration  # 推定時間を保持
                    })
                
                if not scene_assets:
                    print(f"⚠️ シーン素材生成失敗: {title}")
                    return None
                
                # 各アスペクト比で動画生成
                results = {}
                for aspect_ratio in self.aspect_ratios:
                    if aspect_ratio not in self.aspect_ratio_sizes:
                        print(f"⚠️ 解像度が定義されていません: {aspect_ratio}")
                        continue
                    
                    # 解像度取得
                    width, height = self.aspect_ratio_sizes[aspect_ratio]
                    print(f"🎥 動画生成 ({aspect_ratio}, {width}x{height}): {title[:30]}...")
                    
                    # VideoCompositor作成
                    compositor = VideoCompositor(width, height, self.fps, scene_padding=self.tail_sec)
                    
                    # 各シーンの動画を生成
                    scene_videos = []
                    for scene in scene_assets:
                        # 画像パス
                        image_path = os.path.join(tmpdir, f"scene_{scene['scene_id']}_{aspect_ratio.replace(':', 'x')}.png")
                        
                        # 2. 画像生成 (またはプレースホルダー)
                        if self.generate_images and scene["image_prompt"]:
                            # 画像生成
                            if not self.image_gen.generate(scene["image_prompt"], image_path, aspect_ratio, self.reference_images, self.image_size):
                                print(f"⚠️ 画像生成失敗 -> プレースホルダー使用")
                                self._create_placeholder(image_path, width, height, f"Scene {scene['scene_id']}")
                        else:
                            # プレースホルダー
                            self._create_placeholder(image_path, width, height, f"Scene {scene['scene_id']}")
                        
                        # 3. 動画クリップ生成
                        scene_video_path = os.path.join(tmpdir, f"clip_{scene['scene_id']}_{aspect_ratio.replace(':', 'x')}.mp4")
                        
                        # 推定時間を渡す (ffprobeが失敗した場合に使用される)
                        success = compositor.create_video(
                            image_path=image_path,
                            audio_path=scene["audio_path"],
                            output_path=scene_video_path,
                            telop_text=scene["telop"] if self.telop_config.get("enabled") else None,
                            telop_config=self.telop_config if self.telop_config.get("enabled") else None,
                            duration=scene["estimated_duration"]  # ここで渡す
                        )
                        
                        if success:
                            scene_videos.append(scene_video_path)
                    
                    if not scene_videos:
                        print(f"⚠️ シーン動画生成失敗 ({aspect_ratio}): {title}")
                        continue
                    
                    # シーンを連結
                    temp_video_path = os.path.join(tmpdir, f"temp_{aspect_ratio.replace(':', 'x')}.mp4")
                    if len(scene_videos) == 1:
                        shutil.copy(scene_videos[0], temp_video_path)
                    else:
                        self._concat_videos(scene_videos, temp_video_path)
                    
                    # BGM合成
                    final_video_path = os.path.join(tmpdir, f"final_{aspect_ratio.replace(':', 'x')}.mp4")
                    if self.bgm_config.get("enabled", False):
                        self._add_bgm(temp_video_path, final_video_path)
                    else:
                        shutil.move(temp_video_path, final_video_path)
                    
                    # ストレージに保存
                    aspect_suffix = aspect_ratio.replace(':', 'x')
                    filename = f"videos/{file_base_name}_video_{aspect_suffix}.mp4"
                    storage_path = save_file(
                        open(final_video_path, "rb").read(),
                        filename,
                        "video/mp4"
                    )
                    
                    print(f"✅ 動画生成成功 ({aspect_ratio}): {title[:30]}... -> {storage_path}")
                    
                    # 結果に追加
                    key = f"video_path_{aspect_ratio.replace(':', '_')}"
                    results[key] = storage_path
            
            if not results:
                print(f"❌ すべてのアスペクト比で動画生成失敗: {title}")
                return None
            
            return {
                **results,
                "script_title": script_title,
                "scene_count": len(beats),
                "aspect_ratios": self.aspect_ratios,
                "mime_type": "video/mp4"
            }
            
        except Exception as e:
            print(f"❌ 動画生成エラー: {article.get('title', 'unknown')} | {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_placeholder(self, path: str, width: int, height: int, text: str = ""):
        """プレースホルダー画像を生成"""
        img = Image.new("RGB", (width, height), "#f3f4f6")
        draw = ImageDraw.Draw(img)
        
        # 中央に四角
        box_size = min(width, height) // 4
        left = (width - box_size) // 2
        top = (height - box_size) // 2
        draw.rectangle(
            [(left, top), (left + box_size, top + box_size)],
            outline="#d1d5db",
            width=6
        )
        
        # テキスト描画 (オプション)
        if text:
            try:
                font = ImageFont.load_default()
                draw.text((left, top - 20), text, fill="#000000", font=font)
            except:
                pass
        
        img.save(path, "PNG")
    
    def _concat_videos(self, video_paths: list, output_path: str):
        """複数の動画を連結"""
        list_file = output_path + ".txt"
        with open(list_file, "w") as f:
            for video_path in video_paths:
                f.write(f"file '{video_path}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        os.remove(list_file)

    def _safe_len_seconds(self, text: str) -> float:
        """テキスト長から秒数を推定"""
        n = max(1, len(text or ""))
        sec = n / 6.0  # 1秒あたり6文字と仮定
        return float(f"{max(MIN_SCENE_SEC, min(MAX_SCENE_SEC, sec)):.2f}")

    def _generate_silent_mp3(self, out_mp3: str, seconds: float) -> None:
        """無音MP3を生成"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{seconds:.2f}",
            "-c:a", "libmp3lame", "-b:a", "192k",
            "-ar", "48000", "-ac", "2",
            out_mp3,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Silent narration saved: {out_mp3} ({seconds}s)")
        except subprocess.CalledProcessError as e:
            print(f"❌ Silent narration failed: {e}")

    def _add_bgm(self, video_path: str, output_path: str):
        """動画にBGMを追加（ループ再生、音量調整、フェードアウト、余韻）"""
        bgm_path = self.bgm_config.get("file_path", "")
        volume = self.bgm_config.get("volume", 0.1)
        
        if not bgm_path or not os.path.exists(bgm_path):
            print(f"⚠️ BGMファイルが見つかりません: {bgm_path}")
            shutil.copy(video_path, output_path)
            return

        print(f"🎵 BGM合成: {bgm_path} (Vol: {volume})")
        
        try:
            duration = self._get_video_duration(video_path)
            
            # 動画と音声に余韻を追加し、BGMをミックス
            # 動画の長さを基準にする(BGMが短くても動画は切れない)
            fc = (
                f"[0:v]tpad=stop_mode=clone:stop_duration={self.tail_sec}[v1];"
                f"[0:a]asetpts=PTS-STARTPTS,apad=pad_dur={self.tail_sec},volume=1.0[a0];"
                f"[1:a]asetpts=PTS-STARTPTS,apad=pad_dur={self.tail_sec},volume={volume}[a1];"
                f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-stream_loop", "-1", "-i", bgm_path,
                "-filter_complex", fc,
                "-map", "[v1]", "-map", "[aout]",
                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(duration + self.tail_sec),  # 動画の長さを明示的に指定
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception as e:
            print(f"⚠️ BGM合成失敗: {e}")
            shutil.copy(video_path, output_path)

    def _get_video_duration(self, path: str) -> float:
        """動画の長さを取得"""
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except:
            return 0.0
