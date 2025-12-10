# -*- coding: utf-8 -*-
"""
OMO Platform - 変換基底クラス (フィルタリング対応版)

全ての変換処理が継承する抽象基底クラス
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.common.filters import ArticleFilter


class BaseTransformer(ABC):
    """変換基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 変換設定 (YAMLから読み込まれた辞書)
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        
        # フィルタ設定
        filter_config = config.get("filters", {})
        self.filter = ArticleFilter(filter_config) if filter_config else None
    
    def transform_with_filter(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        フィルタリングを含めた変換実行
        
        Args:
            article: Firestoreから取得した記事データ
        
        Returns:
            変換結果の辞書 (失敗時またはフィルタで除外された場合はNone)
        """
        # フィルタチェック
        if self.filter and not self.filter.should_include(article):
            title = article.get("title", "unknown")
            print(f"⏭️ フィルタによりスキップ: {title[:50]}...")
            return None
        
        # 実際の変換処理
        return self.transform(article)
    
    @abstractmethod
    def transform(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        変換を実行
        
        Args:
            article: Firestoreから取得した記事データ
        
        Returns:
            変換結果の辞書 (失敗時はNone)
        """
        pass
    
    def is_enabled(self) -> bool:
        """変換が有効かどうか"""
        return self.enabled
    
    def get_transform_type(self) -> str:
        """変換タイプを取得"""
        return self.__class__.__name__
    
    def validate_article(self, article: Dict[str, Any]) -> bool:
        """
        記事データが変換可能かバリデーション
        
        Args:
            article: 記事データ
        
        Returns:
            変換可能ならTrue
        """
        # 基本的なフィールドの存在チェック
        required_fields = ["title", "body_text"]
        return all(article.get(field) for field in required_fields)
