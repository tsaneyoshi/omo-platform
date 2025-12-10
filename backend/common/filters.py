# -*- coding: utf-8 -*-
"""
OMO Platform - フィルタリング機能

記事をブラックリスト/ホワイトリストでフィルタリング
"""

from typing import Dict, Any, List, Optional


class ArticleFilter:
    """記事フィルタリング"""
    
    def __init__(self, filter_config: Dict[str, Any]):
        """
        Args:
            filter_config: フィルタ設定
                {
                    "mode": "blacklist" | "whitelist" | "both",
                    "blacklist": {"title": [...], "category": [...]},
                    "whitelist": {"title": [...], "category": [...]}
                }
        """
        self.mode = filter_config.get("mode", "blacklist")
        self.blacklist = filter_config.get("blacklist", {})
        self.whitelist = filter_config.get("whitelist", {})
    
    def should_include(self, article: Dict[str, Any]) -> bool:
        """
        記事を含めるべきか判定
        
        Args:
            article: 記事データ
        
        Returns:
            True: 含める, False: 除外
        """
        title = article.get("title", "")
        category = article.get("category", "")
        
        if self.mode == "blacklist":
            return self._check_blacklist(title, category)
        
        elif self.mode == "whitelist":
            return self._check_whitelist(title, category)
        
        elif self.mode == "both":
            # ホワイトリスト優先
            if self._check_whitelist(title, category):
                return True
            return self._check_blacklist(title, category)
        
        return True
    
    def _check_blacklist(self, title: str, category: str) -> bool:
        """ブラックリストチェック (該当すれば除外)"""
        # タイトルチェック
        title_blacklist = self.blacklist.get("title", [])
        for keyword in title_blacklist:
            if keyword in title:
                return False  # 除外
        
        # カテゴリチェック
        category_blacklist = self.blacklist.get("category", [])
        for keyword in category_blacklist:
            if keyword in category:
                return False  # 除外
        
        return True  # 含める
    
    def _check_whitelist(self, title: str, category: str) -> bool:
        """ホワイトリストチェック (該当すれば含める)"""
        # タイトルチェック
        title_whitelist = self.whitelist.get("title", [])
        for keyword in title_whitelist:
            if keyword in title:
                return True  # 含める
        
        # カテゴリチェック
        category_whitelist = self.whitelist.get("category", [])
        for keyword in category_whitelist:
            if keyword in category:
                return True  # 含める
        
        return False  # 除外
