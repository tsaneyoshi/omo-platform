# -*- coding: utf-8 -*-
"""
OMO Platform - HTTP共通処理モジュール

スクレイピング用のHTTP操作を提供
"""

import requests
from typing import Optional, Dict
from bs4 import BeautifulSoup, UnicodeDammit


class HTTPClient:
    """HTTP操作クライアント"""
    
    def __init__(self, user_agent: Optional[str] = None):
        """
        Args:
            user_agent: User-Agent文字列
        """
        self.user_agent = user_agent or "OMO-Platform/1.0 (+https://github.com/YOUR_USERNAME/omo-platform)"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
    
    def get(
        self,
        url: str,
        timeout: int = 20,
        **kwargs
    ) -> requests.Response:
        """
        HTTP GETリクエスト
        
        Args:
            url: URL
            timeout: タイムアウト(秒)
            **kwargs: requests.getに渡す追加引数
        
        Returns:
            requests.Response
        
        Raises:
            requests.HTTPError: HTTPエラー
        """
        response = self.session.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    
    def get_soup(
        self,
        url: str,
        timeout: int = 20,
        parser: str = "html.parser"
    ) -> BeautifulSoup:
        """
        URLからBeautifulSoupオブジェクトを取得
        
        Args:
            url: URL
            timeout: タイムアウト(秒)
            parser: HTMLパーサー
        
        Returns:
            BeautifulSoup
        """
        response = self.get(url, timeout=timeout)
        
        # 文字エンコーディングを自動検出
        dammit = UnicodeDammit(response.content, is_html=True)
        html = dammit.unicode_markup or response.text
        
        return BeautifulSoup(html, parser)
    
    def download_binary(
        self,
        url: str,
        timeout: int = 60
    ) -> bytes:
        """
        バイナリファイルをダウンロード
        
        Args:
            url: URL
            timeout: タイムアウト(秒)
        
        Returns:
            バイナリデータ
        """
        response = self.get(url, timeout=timeout)
        return response.content


# グローバルインスタンス
_http_client: Optional[HTTPClient] = None


def get_http_client(user_agent: Optional[str] = None) -> HTTPClient:
    """
    HTTPクライアントを取得
    
    Args:
        user_agent: User-Agent文字列
    
    Returns:
        HTTPClient インスタンス
    """
    global _http_client
    
    if _http_client is None:
        _http_client = HTTPClient(user_agent)
    
    return _http_client
