# -*- coding: utf-8 -*-
"""
OMO Platform - Scrapeオーケストレーター

複数の情報源からスクレイピングを実行し、Firestoreに保存
"""

import sys
from pathlib import Path

# パスを追加 (Cloud Functionsでも動作するように)
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import get_config
from common.firestore import get_firestore_client
from scrape.sources.municipal.moriya import MoriyaScraper


def main():
    """メイン処理"""
    print("🚀 OMO Platform - Scrape開始")
    
    # 設定とクライアントを初期化
    config = get_config()
    firestore_client = get_firestore_client(config)
    
    print(f"📍 自治体: {config.municipality_name}")
    print(f"📦 コレクション: {config.firestore_collection_name}")
    
    # スクレイパーを初期化
    scrapers = []
    
    # 自治体HP
    if config.is_source_enabled("municipal_website"):
        municipal_config = config.get_source_config("municipal_website")
        print(f"   [DEBUG] Municipal Config: {municipal_config}")
        scraper_type = municipal_config.get("scraper", "moriya")
        
        if scraper_type == "moriya":
            scrapers.append(MoriyaScraper(municipal_config))
        else:
            print(f"⚠️ 未対応のスクレイパー: {scraper_type}")
    
    # TODO: SNSスクレイパーを追加
    # if config.is_source_enabled("twitter"):
    #     twitter_config = config.get_source_config("twitter")
    #     scrapers.append(TwitterScraper(twitter_config))
    
    if not scrapers:
        print("⚠️ 有効なスクレイパーがありません")
        return
    
    # スクレイピング実行
    total_articles = 0
    
    for scraper in scrapers:
        try:
            articles = scraper.scrape()
            
            # Firestoreに保存
            for article in articles:
                doc_id = article.pop("doc_id")
                
                # 変更検出付き保存
                status = firestore_client.save_with_hash_check(
                    doc_id=doc_id,
                    new_data=article,
                    hash_field="quick_hash"
                )
                
                if status in ("new", "updated"):
                    total_articles += 1
            
        except Exception as e:
            print(f"❌ スクレイパーエラー ({scraper.get_source_type()}): {e}")
    
    print(f"\n✅ Scrape完了: {total_articles} 件処理")


# Cloud Functions用ハンドラ
def main_handler(request):
    """
    Cloud Functions (Gen2) 用HTTPハンドラ
    
    Args:
        request: flask.Request
    
    Returns:
        (response_body, status_code)
    """
    try:
        main()
        return ("OK", 200)
    except Exception as e:
        print(f"⚠️ main_handler 例外: {e}")
        return (f"ERROR: {e}", 500)


# ローカル実行
if __name__ == "__main__":
    main()
