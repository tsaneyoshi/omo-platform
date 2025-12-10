# -*- coding: utf-8 -*-
"""
OMO Platform - Transformオーケストレーター

スクレイプされた記事を各種フォーマットに変換
"""

import sys
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import get_config
from common.firestore import get_firestore_client
from transform.text.simple import SimpleTextTransformer
from transform.text.easy import EasyTextTransformer
from transform.text.script import ScriptTransformer
from transform.image.single import ImageSingleTransformer
from transform.video.short import VideoShortTransformer


def main():
    """メイン処理"""
    print("🚀 OMO Platform - Transform開始")
    
    # 設定とクライアントを初期化
    config = get_config()
    firestore_client = get_firestore_client(config)
    
    print(f"📍 自治体: {config.municipality_name}")
    print(f"📦 コレクション: {config.firestore_collection_name}")
    
    # 変換対象のドキュメントを取得
    # scriptStatus == None かつ scrapeStatus in ["new", "updated"]
    docs = firestore_client.query_pending_transform(limit=config.batch_limit)
    
    if not docs:
        print("⚠️ 変換対象の記事がありません")
        return
    
    print(f"📝 変換対象: {len(docs)} 件")
    
    # 変換器を初期化
    transformers = {}
    
    # テキスト要約
    if config.is_transform_enabled("text_simple"):
        text_config = config.get_transform_config("text_simple")
        transformers["text_simple"] = SimpleTextTransformer(text_config)
    
    # わかりやすいテキスト
    if config.is_transform_enabled("text_easy"):
        easy_config = config.get_transform_config("text_easy")
        transformers["text_easy"] = EasyTextTransformer(easy_config)
    
    # 台本生成
    if config.is_transform_enabled("text_script"):
        script_config = config.get_transform_config("text_script")
        transformers["text_script"] = ScriptTransformer(script_config)
    
    # 画像変換
    if config.is_transform_enabled("image_single"):
        image_config = config.get_transform_config("image_single")
        transformers["image_single"] = ImageSingleTransformer(image_config)
    
    # 動画変換
    if config.is_transform_enabled("video_short"):
        video_config = config.get_transform_config("video_short")
        transformers["video_short"] = VideoShortTransformer(video_config)
    
    if not transformers:
        print("⚠️ 有効な変換器がありません")
        return
    
    # 変換実行
    success_count = 0
    
    for doc in docs:
        doc_id = doc.id
        article = doc.to_dict()
        article["id"] = doc_id  # IDを追加 (画像保存などで使用)
        
        print(f"\n--- {article.get('title', 'unknown')[:50]}... ---")
        
        try:
            # 変換結果を格納
            transformed_content = {}
            transform_status = {}
            
            # 各変換器を実行 (フィルタリング対応)
            for transform_type, transformer in transformers.items():
                # transform_with_filterを使用 (フィルタチェック込み)
                result = transformer.transform_with_filter(article)
                
                if result:
                    transformed_content[transform_type] = result
                    transform_status[transform_type] = "completed"
                    # articleを更新 (次の変換で使用)
                    article["transformedContent"] = transformed_content
                else:
                    transform_status[transform_type] = "skipped_or_failed"
            
            # Firestoreに保存
            if transformed_content:
                update_data = {
                    "transformedContent": transformed_content,
                    "transformStatus": transform_status,
                    "scriptStatus": True,  # 変換完了フラグ (既存との互換性)
                }
                
                firestore_client.update_document(doc_id, update_data)
                print(f"✅ 変換完了: {doc_id}")
                success_count += 1
            else:
                print(f"⚠️ 変換失敗: {doc_id}")
        
        except Exception as e:
            print(f"❌ エラー: {doc_id} | {e}")
    
    print(f"\n✅ Transform完了: {success_count}/{len(docs)} 件成功")


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
