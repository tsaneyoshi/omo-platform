# -*- coding: utf-8 -*-
"""
OMO Platform - 動画合成 (FFmpeg)

画像 + 音声 + テロップ → 動画
"""

import os
import subprocess
import tempfile
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont


class VideoCompositor:
    """動画合成"""
    
    def __init__(self, width: int, height: int, fps: int = 30, scene_padding: float = 0.6):
        """
        Args:
            width: 動画幅
            height: 動画高さ
            fps: フレームレート
            scene_padding: 各シーンの末尾余韻(秒)
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.scene_padding = scene_padding
    
    def create_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        telop_text: str = None,
        telop_config: dict = None,
        duration: Optional[float] = None  # 追加: 外部から時間を指定可能に
    ) -> bool:
        """
        動画を生成
        
        Args:
            image_path: 背景画像パス
            audio_path: 音声ファイルパス
            output_path: 出力動画パス
            telop_text: テロップテキスト
            telop_config: テロップ設定
            duration: 動画の長さ(秒)。Noneの場合は音声ファイルから取得
        
        Returns:
            成功したらTrue
        """
        try:
            # 音声の長さを取得 (指定がない場合)
            if duration is None or duration <= 0:
                probed_duration = self._get_audio_duration(audio_path)
                if probed_duration > 0:
                    duration = probed_duration
            
            # それでも取得できない場合
            if duration is None or duration <= 0:
                print(f"⚠️ 音声の長さが特定できません: {audio_path}")
                # ファイルサイズを確認
                if os.path.exists(audio_path):
                    size = os.path.getsize(audio_path)
                    print(f"   ファイルサイズ: {size} bytes")
                else:
                    print("   ファイルが存在しません")
                return False
            
            print(f"   [DEBUG] Audio duration: {duration:.2f}s (probed from file)")
            
            # 画像をリサイズ
            resized_image = self._resize_image(image_path)
            
            # テロップ付き画像を生成
            if telop_text and telop_config:
                final_image = self._add_telop(resized_image, telop_text, telop_config)
            else:
                final_image = resized_image
            
            # 一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_image_path = tmp.name
                final_image.save(tmp_image_path)
            
            try:
                # FFmpegで動画生成
                self._run_ffmpeg(tmp_image_path, audio_path, output_path, duration)
                return True
            finally:
                # 一時ファイル削除
                if os.path.exists(tmp_image_path):
                    os.remove(tmp_image_path)
        
        except Exception as e:
            print(f"❌ 動画生成エラー: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """音声の長さを取得 (秒)"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️ ffprobe失敗: {result.stderr}")
                self._log_file_details(audio_path)
                return 0.0
            
            stdout = result.stdout.strip()
            if not stdout or stdout == "N/A":
                print(f"⚠️ ffprobe出力が無効です (N/A): {audio_path}")
                self._log_file_details(audio_path)
                return 0.0
                
            return float(stdout)
        except Exception as e:
            print(f"⚠️ ffprobe実行エラー: {e}")
            return 0.0

    def _log_file_details(self, path: str):
        """ファイルの先頭バイトなどをログ出力"""
        if not os.path.exists(path):
            print(f"   ファイルが存在しません: {path}")
            return
            
        size = os.path.getsize(path)
        print(f"   ファイルサイズ: {size} bytes")
        
        try:
            with open(path, "rb") as f:
                head = f.read(16)
                hex_head = " ".join(f"{b:02X}" for b in head)
                print(f"   Magic Number (Hex): {hex_head}")
                
            # Run verbose ffprobe
            print("   Running verbose ffprobe...")
            cmd = ["ffprobe", "-hide_banner", path]
            subprocess.run(cmd, capture_output=False) # Print to stdout/stderr directly
            
        except Exception as e:
            print(f"   詳細ログ出力失敗: {e}")
    
    def _resize_image(self, image_path: str) -> Image.Image:
        """画像をリサイズ/クロップ"""
        img = Image.open(image_path).convert("RGB")
        
        # アスペクト比を維持してリサイズ
        img_ratio = img.width / img.height
        target_ratio = self.width / self.height
        
        if img_ratio > target_ratio:
            # 画像が横長 → 高さを合わせてクロップ
            new_height = self.height
            new_width = int(new_height * img_ratio)
        else:
            # 画像が縦長 → 幅を合わせてクロップ
            new_width = self.width
            new_height = int(new_width / img_ratio)
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 中央クロップ
        left = (new_width - self.width) // 2
        top = (new_height - self.height) // 2
        img = img.crop((left, top, left + self.width, top + self.height))
        
        return img
    
    def _add_telop(self, img: Image.Image, text: str, config: dict) -> Image.Image:
        """テロップを追加"""
        # 新しい画像を作成 (元の画像をコピー)
        result = img.copy()
        draw = ImageDraw.Draw(result)
        
        # フォント設定
        font_path = config.get("font_path")
        font_size = config.get("font_size", 72)
        font_color = config.get("font_color", "#ffffff")
        box_color = config.get("box_color", "#000000")
        box_opacity = config.get("box_opacity", 0.6)
        position = config.get("position", "top")
        margin_top = config.get("margin_top", 100)
        margin_bottom = config.get("margin_bottom", 160)
        align = config.get("align", "center")  # テキスト配置: "left", "center", "right"
        
        # フォント読み込み
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                # デフォルトフォント
                font = ImageFont.load_default()
        except Exception as e:
            print(f"⚠️ フォント読み込み失敗: {e}")
            font = ImageFont.load_default()
        
        # テキストの折り返し処理
        max_width_ratio = config.get("max_width_ratio", 0.9)
        max_width = self.width * max_width_ratio
        wrapped_text = self._wrap_text(text, font, max_width, draw)
        
        # 行ごとのサイズを計算
        lines = wrapped_text.split('\n')
        line_heights = []
        line_widths = []
        total_height = 0
        max_line_width = 0
        
        line_spacing = config.get("line_spacing", 10)
        
        # フォントメトリクスを取得（一貫した行の高さのため）
        try:
            ascent, descent = font.getmetrics()
            line_height = ascent + descent
        except:
            # デフォルトフォントの場合はbboxから計算
            line_height = None
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_widths.append(w)
            
            # 一貫した高さを使用（メトリクスが取得できた場合）
            if line_height is not None:
                line_heights.append(line_height)
                total_height += line_height
            else:
                line_heights.append(h)
                total_height += h
            
            max_line_width = max(max_line_width, w)
            
        total_height += line_spacing * (len(lines) - 1)
        
        # 全体の位置計算
        if position == "top":
            start_y = margin_top
        elif position == "bottom":
            start_y = self.height - margin_bottom - total_height
        else:  # center
            start_y = (self.height - total_height) // 2
            
        # 背景ボックス
        padding = config.get("padding", 20)
        
        # ボックスの幅を固定 (max_width_ratio を使用)
        box_width = max_width + padding * 2
        
        # 背景ボックスは常に中央配置
        box_left = (self.width - box_width) // 2
        box_right = box_left + box_width
        
        box_top = start_y - padding
        box_bottom = start_y + total_height + padding
        
        # 半透明ボックス
        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        box_rgb = self._hex_to_rgb(box_color)
        box_rgba = box_rgb + (int(255 * box_opacity),)
        
        overlay_draw.rectangle(
            [(box_left, box_top), (box_right, box_bottom)],
            fill=box_rgba
        )
        
        # 合成
        result = Image.alpha_composite(result.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(result)
        
        # テキスト描画 (行ごと)
        current_y = start_y
        text_rgb = self._hex_to_rgb(font_color)
        
        for i, line in enumerate(lines):
            line_w = line_widths[i]
            
            # 配置に応じてX座標を計算 (背景ボックス内での位置)
            if align == "left":
                x = box_left + padding
            elif align == "right":
                x = box_right - line_w - padding
            else:  # center
                x = (self.width - line_w) // 2
            
            draw.text((x, current_y), line, font=font, fill=text_rgb)
            current_y += line_heights[i] + line_spacing
            
        return result

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
        """テキストを指定幅で折り返す(既存の改行は無視)"""
        lines = []
        
        # すべての改行を削除して1つの段落として扱う
        clean_text = text.replace('\n', '').replace('\r', '').strip()
        
        if not clean_text:
            return ""
        
        line = ""
        for char in clean_text:
            test_line = line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            
            if w <= max_width:
                line = test_line
            else:
                if line:  # 空行を避ける
                    lines.append(line)
                line = char
        
        if line:  # 最後の行を追加
            lines.append(line)
        
        return "\n".join(lines)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """HEX色をRGBに変換"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _run_ffmpeg(self, image_path: str, audio_path: str, output_path: str, duration: float):
        """FFmpegで動画生成"""
        print(f"   [DEBUG] Creating video with audio padding: {self.scene_padding}s")
        
        # 音声に余韻(無音)を追加するフィルター
        # これにより、音声の実際の長さ + 余韻が保証される
        audio_filter = f"apad=pad_dur={self.scene_padding}"
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-filter:a", audio_filter,  # 音声に余韻を追加
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",  # 音声の長さに合わせる
            "-r", str(self.fps),
            output_path
        ]
        
        # print(f"🚀 FFmpeg: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFmpeg失敗:")
            print(result.stderr)
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        
        # print(f"✅ 動画生成完了: {output_path}")
