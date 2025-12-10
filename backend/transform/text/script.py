# -*- coding: utf-8 -*-
"""
OMO Platform - 台本生成 (MulmoScript)

記事から動画用の台本を生成
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.transform.core.base import BaseTransformer
from backend.common.config import get_config
from backend.common.utils import truncate_text
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold


class ScriptTransformer(BaseTransformer):
    """台本生成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.municipality_name = config.get("municipality_name", "守谷市")
        self.character_name = config.get("character_name", "こじゅまる")
        self.scene_min = config.get("scene_min", 3)
        self.scene_max = config.get("scene_max", 10)
        self.model_name = config.get("model_name", "gemini-2.5-pro")
        self.telop_max_chars = config.get("telop_max_chars", 40)
        self.max_output_tokens = config.get("max_output_tokens", 16384)
        self.prompts = config.get("prompts", {})
        
        # Gemini初期化
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY が設定されていません")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)
        print(f"✨ ScriptTransformer初期化: model={self.model_name}")
        
        # 安全設定 (ブロックなし)
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

    # ... (中略) ...

    def _generate_script(self, scene_count: int, title: str, body_text: str) -> Optional[Dict[str, Any]]:
        """台本生成"""
        
        template = self.prompts.get("script", """
あなたはプロの放送作家です。
以下の記事を元に、ショート動画（TikTok/Reels/Shorts用）の台本を作成してください。

# 記事タイトル
{title}

# 記事本文
{body_text}

# 制約事項
- 自治体名: {municipality_name}
- キャラクター: {character_name}（語尾は「だワン」「だじょ」など親しみやすく）
- ターゲット: 若い世代〜子育て世代
- 尺: 30秒〜60秒程度
- 構成:
  1. 導入（フック）: 視聴者の興味を惹く
  2. 本題: 記事の要点を分かりやすく
  3. 結び: 行動喚起（詳細はWebで、など）
- シーン数: {scene_min}〜{scene_max}シーン

# 出力フォーマット (JSON)
{{
  "title": "動画タイトル",
  "beats": [
    {{
      "scene": 1,
      "narration": "ナレーション（読み上げ用テキスト）",
      "visual_prompt": "画像生成AIへの指示（英語、詳細に）"
    }},
    ...
  ]
}}
""")
        
        prompt = template.format(
            title=title,
            body_text=truncate_text(body_text, 3000),
            municipality_name=self.municipality_name,
            character_name=self.character_name,
            scene_min=self.scene_min,
            scene_max=self.scene_max
        )

        # ... (API呼び出し部分はそのまま) ...

    def _generate_telops(self, script_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """テロップ生成"""
        
        script_json = json.dumps(script_data, ensure_ascii=False, indent=2)
        
        template = self.prompts.get("telop", """
以下の動画台本の各シーンに合わせて、画面に表示するテロップ（字幕）を作成してください。

# 台本データ
{script_json}

# 制約事項
- 1シーンにつき1つのテロップ
- 文字数制限: {telop_max_chars}文字以内
- 視認性を重視し、要点を短くまとめる
- 絵文字の使用はOK

# 出力フォーマット (JSON配列)
[
  {{
    "scene": 1,
    "telop_text": "テロップテキスト"
  }},
  ...
]
""")
        print(f"DEBUG: telop template: {template}")
        
        prompt = template.format(
            script_json=script_json,
            telop_max_chars=self.telop_max_chars
        )
        
        try:
            config = GenerationConfig(
                temperature=0.0,
                max_output_tokens=10240
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=config,
                safety_settings=self.safety_settings
            )
            
            raw = self._extract_text_safe(response)
            if not raw:
                raise ValueError("Empty response")
                
            # JSON配列抽出 (堅牢版)
            telops = self._extract_json_array(raw)
            if not telops:
                # 失敗時のログ
                print(f"⚠️ JSONパース失敗 Raw: {raw[:200]}...")
                raise ValueError("JSON parsing failed")
                
            print(f"✅ テロップ生成完了: {len(telops)}シーン")
            return telops
            
        except Exception as e:
            print(f"⚠️ テロップ生成失敗: {e}")
            # フォールバック: テキストをそのまま短縮して使う
            fallback_telops = []
            for i, beat in enumerate(beats):
                text = beat.get("text", "")
                fallback_telops.append({
                    "id": i+1,
                    "should_telop": True,
                    "telop_text": text[:40] + "..." if len(text) > 40 else text,
                    "category": "FALLBACK",
                    "confidence": 0.5,
                    "reason": "Generation failed"
                })
            return fallback_telops
    
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        記事から台本を生成
        """
        if not self.is_enabled():
            return None
            
        if not self.validate_article(article):
            print(f"⚠️ 記事データが不正: {article.get('title', 'unknown')}")
            return None
        
        try:
            title = article.get("title", "")
            body_text = article.get("body_text", "")
            
            print(f"📝 台本生成開始: {title[:30]}...")
            
            # 1. シーン数を決定
            scene_count = self._get_scene_count(title, body_text)
            
            # 2. 台本生成
            script_data = self._generate_script(scene_count, title, body_text)
            if not script_data:
                return None
            
            # 3. テロップ生成
            telops = self._generate_telops(script_data)
            
            # テロップを台本に統合
            beats = script_data.get("beats", [])
            for i, beat in enumerate(beats):
                if i < len(telops):
                    beat["telop"] = telops[i].get("telop_text", "")
                else:
                    beat["telop"] = ""
            
            if not script_data.get("beats"):
                print(f"⚠️ 台本生成失敗: {title}")
                return None
            
            print(f"✅ 台本生成完了: {title[:30]}... ({len(beats)}シーン)")
            return script_data
            
        except Exception as e:
            print(f"❌ 台本生成エラー: {article.get('title', 'unknown')} | {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_scene_count(self, title: str, body_text: str) -> int:
        """シーン数を決定"""
        input_text = f"記事タイトル: {title}\n\n記事本文:\n{truncate_text(body_text, 800)}"
        
        template = self.prompts.get("scene_count", """あなたはプロの構成作家です。
以下の記事の要点を分析し、ショート動画で最も効果的に伝えるための最適なシーン数を提案してください。

# 記事の要点
{input_text}

# 指示
- 回答は **半角整数のみ**。他の文字・空白・句読点は一切含めないこと。
- 許容範囲は {scene_min}〜{scene_max}。

# 回答:
""")
        
        prompt = template.format(
            input_text=input_text,
            scene_min=self.scene_min,
            scene_max=self.scene_max
        )
        
        try:
            print(f"🔢 シーン数取得開始 (model={self.model_name})")
            config = GenerationConfig(
                temperature=0.0,
                max_output_tokens=10240
            )
            
            # 初回試行
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=config,
                    safety_settings=self.safety_settings
                )
                raw = self._extract_text_safe(response)
            except Exception as e:
                print(f"⚠️ 初回試行失敗: {e}")
                raw = ""

            # 失敗時のリトライ (プロンプト調整)
            if not raw:
                print("⚠️ シーン数取得失敗 -> リトライ (プロンプト調整)")
                safe_prompt = prompt + "\n\n※内容評価や不適切表現は扱わず、数値だけを出力してください。"
                try:
                    response = self.model.generate_content(
                        safe_prompt,
                        generation_config=config,
                        safety_settings=self.safety_settings
                    )
                    raw = self._extract_text_safe(response)
                except Exception as e:
                    print(f"⚠️ リトライ失敗: {e}")
                    raw = ""
            
            # 数字を抽出
            if raw:
                m = re.search(r'\d+', raw)
                if m:
                    n = int(m.group(0))
                    n = max(self.scene_min, min(self.scene_max, n))
                    print(f"🎬 シーン数: {n}")
                    return n
            
            raise ValueError("no int returned")
        
        except Exception as e:
            print(f"⚠️ シーン数の決定に失敗: {e} → デフォルト使用")
            default_n = max(self.scene_min, min(self.scene_max, 5))
            print(f"   → {default_n}")
            return default_n

    def _extract_text_safe(self, response) -> str:
        """レスポンスから安全にテキストを抽出"""
        try:
            if response.parts:
                return response.text.strip()
        except Exception:
            pass
            
        # candidatesを確認
        if hasattr(response, "candidates") and response.candidates:
            cand = response.candidates[0]
            if cand.finish_reason != 1: # STOP以外
                print(f"   [DEBUG] Finish Reason: {cand.finish_reason}")
                if hasattr(cand, "safety_ratings"):
                    print(f"   [DEBUG] Safety Ratings: {cand.safety_ratings}")
            
            if cand.content and cand.content.parts:
                return cand.content.parts[0].text.strip()
        
        print(f"   [DEBUG] Prompt Feedback: {response.prompt_feedback}")
        return ""
    
    def _generate_script(self, scene_count: int, title: str, body_text: str) -> Optional[Dict]:
        """台本を生成"""
        print(f"📝 台本生成開始 (model={self.model_name}, scenes={scene_count})")
        input_text = f"記事タイトル: {title}\n\n記事本文:\n{truncate_text(body_text, 800)}"
        
        template = self.prompts.get("script", """あなたは、「{municipality_name}」の公式情報を市民に分かりやすく伝えるための、動画台本生成AIです。
以下の入力情報に基づき、全体を正確に {scene_count} シーンで構成したショート動画の台本を作成してください。

### 出力要件（厳守）
- 出力は **JSONのみ**（前後の説明文やコードフェンス禁止）
- ルートのキーは **"model_name"**, **"title"**, **"lang"**, **"beats"** のみ
- **"model_name": "{model_name}"** を必ず含める
- "title": 市民がクリックしたくなる日本語タイトル（「{municipality_name}」を自然に含める、全角35字目安）
- "lang": "ja"

- "beats": 配列で **{scene_count} 要素きっちり**
  - 各要素はオブジェクトで **"text"**（日本語の台詞）と **"imagePrompt"**（背景用の説明）を必須
  - **text** は挨拶や自己紹介を入れず、冒頭から本題へ
  - **text には、入力に含まれる開催日・曜日・時間・会場を「数字・記号」を用いて**正確に**明記すること**
  - "imagePrompt" は、キャラクター（{character_name}）が脇役として登場するように描写すること。
  - **imagePrompt** では、看板やポスター、カレンダーなどに、地名（{municipality_name}）や日付、イベント名などの文字を自然に配置するよう指示してよい。
  - ただし、長文は避け、視認性の高い短い単語や数字を中心に構成すること。
  - スタイル指定は書かない。

### JSON例
{{
  "$mulmocast": {{"version": "1.1"}},
  "title": "【{municipality_name}】…",
  "lang": "ja",
  "beats": [
    {{"text": "…", "imagePrompt": "…"}}
  ]
}}

### 入力情報
{input_text}
""")
        
        prompt = template.format(
            title=title,
            body_text=truncate_text(body_text, 3000),
            municipality_name=self.municipality_name,
            character_name=self.character_name,
            scene_min=self.scene_min,
            scene_max=self.scene_max,
            scene_count=scene_count,
            model_name=self.model_name,
            input_text=input_text # デフォルトテンプレート用
        )
        
        try:
            config = GenerationConfig(
                temperature=0.2,
                top_p=0.9,
                top_k=40,
                max_output_tokens=10240
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=config,
                safety_settings=self.safety_settings
            )
            
            # 安全チェック
            if not response.parts:
                print(f"⚠️ 台本生成ブロック: {response.prompt_feedback}")
                return None
                
            raw = response.text.strip()
            
            # JSONを抽出
            script = self._parse_json(raw)
            
            if not script:
                raise ValueError("JSON parsing failed")
            
            # バリデーション
            if not script.get("beats") or len(script["beats"]) != scene_count:
                print(f"⚠️ シーン数不一致: 期待={scene_count}, 実際={len(script.get('beats', []))}")
            
            return script
            
        except Exception as e:
            print(f"❌ 台本生成失敗: {e}")
            return None

    def _generate_telops(self, script_data: Dict) -> List[Dict]:
        """テロップを生成"""
        beats = script_data.get("beats", [])
        if not beats:
            return []
            
        print(f"📝 テロップ生成開始 (scenes={len(beats)})")
        
        script_json = json.dumps(script_data, ensure_ascii=False, indent=2)
        
        template = self.prompts.get("telop", """
以下の動画台本の各シーンに合わせて、画面に表示するテロップ（字幕）を作成してください。

# 台本データ
{script_json}

# 制約事項
- 1シーンにつき1つのテロップ
- 文字数制限: {telop_max_chars}文字以内
- 視認性を重視し、要点を短くまとめる
- 絵文字の使用はOK

# 出力フォーマット (JSON配列)
[
  {{
    "scene": 1,
    "telop_text": "テロップテキスト"
  }},
  ...
]
""")
        
        prompt = template.format(
            script_json=script_json,
            telop_max_chars=self.telop_max_chars
        )
        
        try:
            config = GenerationConfig(
                temperature=0.0,
                max_output_tokens=self.max_output_tokens
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=config,
                safety_settings=self.safety_settings
            )
            
            raw = self._extract_text_safe(response)
            if not raw:
                raise ValueError("Empty response")
                
            # JSON配列抽出 (堅牢版)
            telops = self._extract_json_array(raw)
            if not telops:
                # 失敗時のログ
                print(f"⚠️ JSONパース失敗 Raw: {raw[:200]}...")
                raise ValueError("JSON parsing failed")
                
            print(f"✅ テロップ生成完了: {len(telops)}シーン")
            return telops
            
        except Exception as e:
            print(f"⚠️ テロップ生成失敗: {e}")
            # フォールバック: テキストをそのまま短縮して使う
            fallback_telops = []
            for i, beat in enumerate(beats):
                text = beat.get("text", "")
                fallback_telops.append({
                    "id": i+1,
                    "should_telop": True,
                    "telop_text": text[:40] + "..." if len(text) > 40 else text,
                    "category": "FALLBACK",
                    "confidence": 0.5,
                    "reason": "Generation failed"
                })
            return fallback_telops

    def _extract_json_array(self, text: str) -> List[Dict]:
        """テキストからJSON配列を抽出"""
        text = text.strip()
        
        # コードフェンス削除
        if "```" in text:
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        
        # そのままパース試行
        try:
            j = json.loads(text)
            if isinstance(j, list): return j
        except:
            pass
            
        # '[' から始まる部分を探してパース
        start = text.find("[")
        while start != -1:
            depth = 0
            in_str = False
            esc = False
            
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc: esc = False
                    elif ch == "\\": esc = True
                    elif ch == '"': in_str = False
                else:
                    if ch == '"': in_str = True
                    elif ch == "[": depth += 1
                    elif ch == "]":
                        depth -= 1
                        if depth == 0:
                            # 候補発見
                            candidate = text[start:i+1]
                            try:
                                j = json.loads(candidate)
                                if isinstance(j, list): return j
                            except:
                                pass
                            break # この '[' からの探索は終了
            
            start = text.find("[", start + 1)
            
        return []
    
    def _parse_json(self, raw: str) -> Optional[Dict]:
        """JSONをパース"""
        # コードフェンスを削除
        s = raw.strip()
        s = re.sub(r'^```(?:json|JSON)?\s*', '', s)
        s = re.sub(r'\s*```$', '', s)
        
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        
        # JSONオブジェクトを抽出
        start = s.find("{")
        if start != -1:
            depth = 0
            in_str = False
            esc = False
            
            for i in range(start, len(s)):
                ch = s[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(s[start:i+1])
                            except Exception:
                                break
        
        return None
