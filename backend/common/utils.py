# -*- coding: utf-8 -*-
"""
OMO Platform - ユーティリティモジュール

共通で使用するヘルパー関数
"""

import hashlib
import re
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone


# ========================================
# ハッシュ計算
# ========================================

def compute_content_hash(*contents: str) -> str:
    """
    複数のコンテンツからハッシュを計算
    
    Args:
        *contents: ハッシュ化する文字列
    
    Returns:
        SHA256ハッシュ (hex)
    """
    combined = "\n".join(str(c) for c in contents)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_quick_hash(
    body_text: str,
    pdf_links: list,
    image_links: list,
    page_title: str = "",
    published_date: str = ""
) -> str:
    """
    軽量ハッシュ計算 (本文 + リンク集合)
    
    Args:
        body_text: 本文テキスト
        pdf_links: PDFリンクのリスト
        image_links: 画像リンクのリスト
        page_title: ページタイトル
        published_date: 公開日
    
    Returns:
        SHA256ハッシュ (hex)
    """
    base = "\n".join([
        page_title.strip(),
        published_date.strip(),
        body_text.strip(),
        "|PDFS|", *sorted(set(pdf_links)),
        "|IMGS|", *sorted(set(image_links)),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ========================================
# JSON処理
# ========================================

def strip_code_fence(text: str) -> str:
    """
    マークダウンのコードフェンスを除去
    
    Args:
        text: 入力テキスト
    
    Returns:
        フェンスを除去したテキスト
    """
    if not text:
        return text
    
    # 全体がフェンスで囲まれている場合
    pattern_anchored = re.compile(r"^\s*```(?:json|JSON)?\s*(.*?)\s*```\s*$", re.DOTALL)
    match = pattern_anchored.match(text)
    if match:
        return match.group(1)
    
    # 途中にフェンスがある場合
    pattern_anywhere = re.compile(r"```(?:json|JSON)?\s*(.*?)\s*```", re.DOTALL)
    match = pattern_anywhere.search(text)
    if match:
        return match.group(1)
    
    return text


def extract_json_object(text: str) -> Optional[str]:
    """
    テキストから最初のJSONオブジェクトを抽出
    
    Args:
        text: 入力テキスト
    
    Returns:
        JSONオブジェクト文字列 (見つからない場合はNone)
    """
    if not text:
        return None
    
    start = text.find("{")
    
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        
        for i in range(start, len(text)):
            ch = text[i]
            
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
        
        start = text.find("{", start + 1)
    
    return None


def parse_json_loose(text: str) -> Dict[str, Any]:
    """
    緩いJSONパース (フェンス除去 + オブジェクト抽出)
    
    Args:
        text: 入力テキスト
    
    Returns:
        パースされた辞書 (失敗時は空辞書)
    """
    if not text:
        return {}
    
    # フェンス除去
    text = strip_code_fence(text.strip())
    
    # 通常のパースを試行
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]
    except Exception:
        pass
    
    # JSONオブジェクトを抽出してパース
    fragment = extract_json_object(text)
    if fragment:
        try:
            parsed = json.loads(fragment)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    
    return {}


# ========================================
# テキスト処理
# ========================================

def normalize_whitespace(text: str) -> str:
    """
    空白文字を正規化
    
    Args:
        text: 入力テキスト
    
    Returns:
        正規化されたテキスト
    """
    if not text:
        return ""
    
    # 改行・タブを空白に
    text = re.sub(r"[\r\n\t]+", " ", text)
    
    # 連続する空白を1つに
    text = re.sub(r"\s{2,}", " ", text)
    
    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "…") -> str:
    """
    テキストを指定長で切り詰め
    
    Args:
        text: 入力テキスト
        max_length: 最大長
        suffix: 切り詰め時の接尾辞
    
    Returns:
        切り詰められたテキスト
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_number(text: str) -> Optional[int]:
    """
    テキストから最初の数値を抽出
    
    Args:
        text: 入力テキスト
    
    Returns:
        抽出された数値 (見つからない場合はNone)
    """
    match = re.search(r"\d+", text or "")
    return int(match.group(0)) if match else None


# ========================================
# 日時処理
# ========================================

def get_current_timestamp() -> datetime:
    """現在のタイムスタンプ (UTC)"""
    return datetime.now(timezone.utc)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    datetimeをフォーマット
    
    Args:
        dt: datetimeオブジェクト
        fmt: フォーマット文字列
    
    Returns:
        フォーマットされた文字列
    """
    return dt.strftime(fmt)


# ========================================
# URL処理
# ========================================

def is_noise_image(url: str) -> bool:
    """
    ノイズ画像かどうかを判定
    
    Args:
        url: 画像URL
    
    Returns:
        ノイズ画像の場合True
    """
    url_lower = url.lower()
    noise_patterns = [
        "logo", "banner", "icon", "btn_", 
        "blank.gif", "newwin1.gif", "spacer.gif"
    ]
    return any(pattern in url_lower for pattern in noise_patterns)


def clean_image_urls(urls: list) -> list:
    """
    画像URLリストからノイズを除去
    
    Args:
        urls: 画像URLのリスト
    
    Returns:
        クリーンな画像URLのリスト
    """
    return [url for url in set(urls) if not is_noise_image(url)]


# ========================================
# デバッグ
# ========================================

def debug_print(message: str, debug: bool = False):
    """
    デバッグ出力
    
    Args:
        message: メッセージ
        debug: デバッグモードフラグ
    """
    if debug:
        print(f"[DEBUG] {message}")


def safe_get(data: Dict, *keys, default=None):
    """
    ネストされた辞書から安全に値を取得
    
    Args:
        data: 辞書
        *keys: キーのパス
        default: デフォルト値
    
    Returns:
        取得された値 (見つからない場合はdefault)
    
    Example:
        safe_get(data, "a", "b", "c", default="")
        # data["a"]["b"]["c"] を安全に取得
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current if current is not None else default
