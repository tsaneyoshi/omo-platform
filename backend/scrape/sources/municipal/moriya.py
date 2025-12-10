# -*- coding: utf-8 -*-
"""
OMO Platform - 守谷市スクレイパー

守谷市公式HPからお知らせをスクレイピング
"""

import hashlib
import sys
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urljoin

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.scrape.core.base import MunicipalScraper
from backend.scrape.core.http import get_http_client
from backend.common.utils import compute_quick_hash, clean_image_urls


class MoriyaScraper(MunicipalScraper):
    """守谷市公式HPスクレイパー"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.http = get_http_client()
        
        # 設定から取得
        self.base_url = config.get("base_url", "https://www.city.moriya.ibaraki.jp")
        self.list_url = config.get("list_url", "https://www.city.moriya.ibaraki.jp/kurashi/oshirase/index.html")
        self.selectors = config.get("selectors", {})
        self.max_per_site = config.get("max_per_site", 10)
    
    def scrape(self) -> List[Dict[str, Any]]:
        """
        スクレイピングを実行
        
        Returns:
            スクレイプされた記事のリスト
        """
        if not self.is_enabled():
            print("⏩ 守谷市スクレイパーは無効です")
            return []
        
        print(f"\n--- 守谷市公式HP ---")
        
        # 一覧取得
        news_list = self.get_news_list()
        
        # 記事詳細を取得
        articles = []
        for info in news_list[:self.max_per_site]:
            try:
                article = self.get_article_detail(
                    url=info["url"],
                    list_title=info.get("list_title", ""),
                    published_date=info.get("date", "")
                )
                
                # ドキュメントID生成
                doc_id = f"moriya_municipal_{hashlib.sha256(info['url'].encode()).hexdigest()}"
                article["doc_id"] = doc_id
                article["category"] = "moriya_municipal"
                article["original_url"] = info["url"]
                article["published_date_str"] = info.get("date", "")
                article["list_title"] = info.get("list_title", "")
                
                articles.append(article)
                
            except Exception as e:
                print(f"❌ 記事取得エラー: {info['url']} | {e}")
        
        print(f"✅ 守谷市: {len(articles)} 件取得")
        return articles
    
    def get_news_list(self) -> List[Dict[str, Any]]:
        """
        お知らせ一覧を取得
        
        Returns:
            お知らせ情報のリスト
        """
        try:
            soup = self.http.get_soup(self.list_url, timeout=20)
            
            # セレクタで一覧アイテムを取得
            items = soup.select(self.selectors.get("list_item_container", "div.list_item"))
            
            results = []
            for item in items:
                # 日付
                date_el = item.select_one(self.selectors.get("date", "span.date"))
                # リンク
                link_el = item.select_one(self.selectors.get("link", "a"))
                
                if not (date_el and link_el):
                    continue
                
                date_text = date_el.get_text(strip=True)
                href = link_el.get("href")
                full_url = urljoin(self.base_url, href)
                link_text = link_el.get_text(strip=True)
                
                results.append({
                    "url": full_url,
                    "date": date_text,
                    "list_title": link_text
                })
            
            print(f"📄 一覧取得: {len(results)} 件")
            return results
            
        except Exception as e:
            print(f"⚠️ 一覧取得失敗: {e}")
            return []
    
    def get_article_detail(
        self,
        url: str,
        list_title: str,
        published_date: str
    ) -> Dict[str, Any]:
        """
        記事詳細を取得
        
        Args:
            url: 記事URL
            list_title: 一覧ページでのタイトル
            published_date: 公開日文字列
        
        Returns:
            記事詳細データ
        """
        soup = self.http.get_soup(url, timeout=20)
        
        # タイトル
        title_el = soup.select_one(self.selectors.get("title", "h1.page_title"))
        page_title = title_el.get_text(strip=True) if title_el else (list_title or "タイトル不明")
        
        # 本文
        content_body = soup.select_one(self.selectors.get("content_body", "div.main_content"))
        body_text = ""
        pdf_links = []
        image_links = []
        
        if content_body:
            # 本文テキスト
            body_text = content_body.get_text(separator="\n", strip=True)
            body_lines = [ln.strip() for ln in body_text.splitlines()]
            body_text = "\n".join([ln for ln in body_lines if ln])
            
            # PDFリンク
            for a in content_body.select('a[href$=".pdf"]'):
                href = a.get("href")
                if href:
                    pdf_links.append(urljoin(self.base_url, href))
            
            # 画像リンク
            for img in content_body.select("img[src]"):
                src = img.get("src")
                if src:
                    image_links.append(urljoin(self.base_url, src))
        
        # ノイズ画像除去
        image_links = clean_image_urls(image_links)
        pdf_links = list(set(pdf_links))
        
        # 軽量ハッシュ計算
        quick_hash = compute_quick_hash(
            body_text=body_text,
            pdf_links=pdf_links,
            image_links=image_links,
            page_title=page_title,
            published_date=published_date
        )
        
        return {
            "title": page_title,
            "body_text": body_text,
            "pdf_links": pdf_links,
            "image_links": image_links,
            "quick_hash": quick_hash,
        }
