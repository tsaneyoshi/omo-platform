# -*- coding: utf-8 -*-
"""
OMO Platform - 設定管理モジュール

YAMLベースの自治体設定と環境変数を統合管理
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()


class Config:
    """設定管理クラス"""
    
    def __init__(self, municipality: Optional[str] = None):
        """
        Args:
            municipality: 自治体名 (例: "moriya")
                         Noneの場合は環境変数 MUNICIPALITY から取得
        """
        self.municipality = municipality or os.getenv("MUNICIPALITY", "moriya")
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """自治体設定ファイルを読み込み"""
        config_path = Path(__file__).parent.parent.parent / "config" / "municipalities" / f"{self.municipality}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"設定ファイルが見つかりません: {config_path}\n"
                f"config/municipalities/{self.municipality}.yaml を作成してください。"
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    # ========================================
    # 自治体情報
    # ========================================
    
    @property
    def municipality_name(self) -> str:
        """自治体名 (例: "守谷市")"""
        return self._config.get("municipality", {}).get("name", "")
    
    @property
    def prefecture(self) -> str:
        """都道府県 (例: "茨城県")"""
        return self._config.get("municipality", {}).get("prefecture", "")
    
    @property
    def character_name(self) -> str:
        """キャラクター名 (例: "こじゅまる")"""
        return self._config.get("municipality", {}).get("character", "")
    
    # ========================================
    # Firestore設定
    # ========================================
    
    @property
    def firestore_project_id(self) -> str:
        """FirestoreプロジェクトID"""
        return os.getenv("FIRESTORE_PROJECT_ID", "")
    
    @property
    def firestore_database_id(self) -> str:
        """FirestoreデータベースID"""
        return os.getenv("FIRESTORE_DATABASE_ID", "(default)")
    
    @property
    def firestore_collection_name(self) -> str:
        """Firestoreコレクション名"""
        return os.getenv("FIRESTORE_COLLECTION_NAME", "omo")
    
    # ========================================
    # Google API設定
    # ========================================
    
    @property
    def google_api_key(self) -> str:
        """Google API Key (Gemini等)"""
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            raise ValueError("環境変数 GOOGLE_API_KEY が設定されていません")
        return key
    
    @property
    def gemini_model_name(self) -> str:
        """Geminiモデル名"""
        return os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")
    
    @property
    def gemini_model_name_mulmoscript(self) -> str:
        """台本生成用Geminiモデル名"""
        return os.getenv("GEMINI_MODEL_NAME_MULMOSCRIPT", self.gemini_model_name)
    
    # ========================================
    # Document AI設定
    # ========================================
    
    @property
    def docai_location(self) -> str:
        """Document AIロケーション"""
        return os.getenv("DOCAI_LOCATION", "us")
    
    @property
    def docai_processor_id(self) -> str:
        """Document AIプロセッサID"""
        return os.getenv("DOCAI_PROCESSOR_ID", "")
    
    @property
    def docai_max_pages(self) -> int:
        """Document AI最大ページ数"""
        return int(os.getenv("DOCAI_MAX_PAGES", "15"))
    
    @property
    def docai_over_limit_policy(self) -> str:
        """Document AIページ上限超過時のポリシー (truncate/skip)"""
        return os.getenv("DOCAI_OVER_LIMIT_POLICY", "truncate")
    
    # ========================================
    # SNS API設定
    # ========================================
    
    @property
    def youtube_api_key(self) -> str:
        """YouTube API Key"""
        return os.getenv("YOUTUBE_API_KEY", "")
    
    @property
    def youtube_channel_id(self) -> str:
        """YouTubeチャンネルID"""
        return os.getenv("YOUTUBE_CHANNEL_ID", "")
    
    @property
    def twitter_bearer_token(self) -> str:
        """Twitter Bearer Token"""
        return os.getenv("TWITTER_BEARER_TOKEN", "")
    
    @property
    def line_channel_access_token(self) -> str:
        """LINE Channel Access Token"""
        return os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    
    @property
    def instagram_access_token(self) -> str:
        """Instagram Access Token"""
        return os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    
    # ========================================
    # 情報源設定
    # ========================================
    
    def get_source_config(self, source_type: str) -> Dict[str, Any]:
        """
        情報源の設定を取得
        
        Args:
            source_type: 情報源タイプ (例: "municipal_hp", "twitter", "youtube")
        
        Returns:
            設定辞書
        """
        return self._config.get("sources", {}).get(source_type, {})
    
    def is_source_enabled(self, source_type: str) -> bool:
        """情報源が有効かどうか"""
        return self.get_source_config(source_type).get("enabled", False)
    
    # ========================================
    # 変換設定
    # ========================================
    
    def get_transform_config(self, transform_type: str) -> Dict[str, Any]:
        """
        変換の設定を取得
        
        Args:
            transform_type: 変換タイプ (例: "text_simple", "image_single")
        
        Returns:
            設定辞書
        """
        return self._config.get("transform", {}).get(transform_type, {})
    
    def is_transform_enabled(self, transform_type: str) -> bool:
        """変換が有効かどうか"""
        return self.get_transform_config(transform_type).get("enabled", False)
    
    # ========================================
    # その他設定
    # ========================================
    
    @property
    def debug(self) -> bool:
        """デバッグモード"""
        return os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    @property
    def batch_limit(self) -> int:
        """バッチ処理の件数制限"""
        return int(os.getenv("BATCH_LIMIT", "5"))
    
    def __repr__(self) -> str:
        return f"Config(municipality='{self.municipality}', name='{self.municipality_name}')"


# グローバルインスタンス (シングルトン的に使用)
_config_instance: Optional[Config] = None


def get_config(municipality: Optional[str] = None) -> Config:
    """
    設定インスタンスを取得
    
    Args:
        municipality: 自治体名 (初回のみ指定可能)
    
    Returns:
        Config インスタンス
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(municipality)
    
    return _config_instance


# 便利な関数
def reload_config(municipality: Optional[str] = None) -> Config:
    """設定を再読み込み"""
    global _config_instance
    _config_instance = Config(municipality)
    return _config_instance
