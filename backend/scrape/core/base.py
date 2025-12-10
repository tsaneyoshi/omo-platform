# -*- coding: utf-8 -*-
"""
OMO Platform - スクレイパー基底クラス

全てのスクレイパーが継承する抽象基底クラス
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseScraper(ABC):
    """スクレイパー基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: スクレイパー設定 (YAMLから読み込まれた辞書)
        """
        self.config = config
        self.enabled = config.get("enabled", False)
    
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        スクレイピングを実行
        
        Returns:
            スクレイプされた記事のリスト
            各記事は以下のフィールドを含む:
            - doc_id: ドキュメントID (Firestore用)
            - title: タイトル
            - original_url: 元URL
            - published_date_str: 公開日文字列
            - その他、スクレイパー固有のフィールド
        """
        pass
    
    def is_enabled(self) -> bool:
        """スクレイパーが有効かどうか"""
        return self.enabled
    
    def get_source_type(self) -> str:
        """情報源タイプを取得"""
        return self.__class__.__name__


class MunicipalScraper(BaseScraper):
    """自治体HP用スクレイパー基底クラス"""
    
    @abstractmethod
    def get_news_list(self) -> List[Dict[str, Any]]:
        """
        お知らせ一覧を取得
        
        Returns:
            お知らせ情報のリスト
            各項目は以下のフィールドを含む:
            - url: 記事URL
            - date: 公開日文字列
            - list_title: 一覧ページでのタイトル
        """
        pass
    
    @abstractmethod
    def get_article_detail(self, url: str, list_title: str, published_date: str) -> Dict[str, Any]:
        """
        記事詳細を取得
        
        Args:
            url: 記事URL
            list_title: 一覧ページでのタイトル
            published_date: 公開日文字列
        
        Returns:
            記事詳細データ
            以下のフィールドを含む:
            - page_title: ページタイトル
            - body_text: 本文テキスト
            - pdf_links: PDFリンクのリスト
            - image_links: 画像リンクのリスト
            - quick_hash: 軽量ハッシュ
        """
        pass


class SocialScraper(BaseScraper):
    """SNS用スクレイパー基底クラス"""
    
    @abstractmethod
    def get_recent_posts(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        最近の投稿を取得
        
        Args:
            max_results: 取得件数
        
        Returns:
            投稿のリスト
        """
        pass
