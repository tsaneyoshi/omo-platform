# -*- coding: utf-8 -*-
"""
OMO Platform - Transform結果リセットスクリプト

スクレイプ直後の状態に戻す(変換結果をすべて削除)
"""

import sys
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import get_config
from common.firestore import get_firestore_client


def reset_transform_fields():
    """変換フィールドをリセット"""
    print("🔄 Transform結果をリセット中...")
    
    # 設定とクライアントを初期化
    config = get_config()
    firestore_client = get_firestore_client(config)
    
    print(f"📍 自治体: {config.municipality_name}")
    print(f"📦 コレクション: {config.firestore_collection_name}")
    
    # すべてのドキュメントを取得
    print("📥 ドキュメントを取得中...")
    all_docs = list(firestore_client.get_collection().stream())
    
    if not all_docs:
        print("⚠️ ドキュメントが見つかりません")
        return
    
    print(f"📄 対象ドキュメント数: {len(all_docs)}")
    print(f"🔍 最初のドキュメントID: {all_docs[0].id}")
    
    # リセット対象のフィールド
    reset_fields = [
        "text_simple",
        "text_easy",
        "image_single",
        "text_script",
        "video_short",
        "transformStatus",
    ]
    
    # バッチ処理
    batch = firestore_client.db.batch()
    count = 0
    
    print(f"🔄 バッチ処理を開始...")
    
    for i, doc in enumerate(all_docs, start=1):
        doc_id = doc.id
        doc_data = doc.to_dict()
        
        if i % 10 == 0:
            print(f"   処理中: {i}/{len(all_docs)}")
        
        # リセットするデータを準備
        update_data = {}
        
        # 変換フィールドを削除(FieldValue.delete()を使用)
        from google.cloud.firestore import DELETE_FIELD
        
        for field in reset_fields:
            if field in doc_data:
                update_data[field] = DELETE_FIELD
        
        # scriptStatusをNoneにリセット
        update_data["scriptStatus"] = None
        
        # 更新がある場合のみバッチに追加
        if update_data:
            doc_ref = firestore_client.get_collection().document(doc_id)
            batch.update(doc_ref, update_data)
            count += 1
            
            # バッチサイズ制限(500件ごとにコミット)
            if count % 450 == 0:
                batch.commit()
                print(f"   ✅ {count} 件コミット済み")
                batch = firestore_client.db.batch()
    
    # 残りをコミット
    if count % 450 != 0:
        batch.commit()
    
    print(f"\n✅ リセット完了: {count} 件のドキュメントを更新しました")
    print(f"📝 リセットしたフィールド: {', '.join(reset_fields)}")
    print(f"🔄 scriptStatus を None にリセットしました")
    print(f"\n次のステップ:")
    print(f"  1. python -m transform.main を実行して変換を再実行")
    print(f"  2. 一枚絵や動画が再生成されます")


if __name__ == "__main__":
    try:
        reset_transform_fields()
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
