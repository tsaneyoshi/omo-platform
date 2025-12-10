# -*- coding: utf-8 -*-
"""
OMO Platform - Firestore操作モジュール

Firestoreの初期化と基本操作を提供
"""

import os
from typing import Optional, Dict, Any, List
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
import google.auth

from .config import get_config


class FirestoreClient:
    """Firestoreクライアントラッパー"""
    
    def __init__(self, config=None):
        """
        Args:
            config: Configインスタンス (Noneの場合は自動取得)
        """
        self.config = config or get_config()
        self.db = self._init_firestore()
        self.collection_name = self.config.firestore_collection_name
        
    def _init_firestore(self) -> firestore.Client:
        """Firestoreクライアントを初期化"""
        try:
            # プロジェクトIDを取得
            project_id = self.config.firestore_project_id
            if not project_id:
                # 環境変数にない場合はADCから取得
                _, project_id = google.auth.default()
            
            database_id = self.config.firestore_database_id
            
            # エミュレータ接続チェック
            emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
            
            if emulator_host:
                # エミュレータ接続
                db = firestore.Client(project=project_id)
                print(f"🧪 Firestore Emulator 接続: {emulator_host}")
                print(f"   project='{project_id}', collection='{self.config.firestore_collection_name}'")
            else:
                # 本番接続
                db = firestore.Client(project=project_id, database=database_id)
                print(f"☁️ Firestore 本番接続: project='{project_id}', database='{database_id}'")
                print(f"   collection='{self.config.firestore_collection_name}'")
            
            return db
            
        except Exception as e:
            raise RuntimeError(f"Firestore 初期化に失敗: {e}")
    
    # ========================================
    # 基本操作
    # ========================================
    
    def get_collection(self):
        """コレクション参照を取得"""
        return self.db.collection(self.collection_name)
    
    def get_document(self, doc_id: str):
        """ドキュメントを取得"""
        return self.get_collection().document(doc_id).get()
    
    def set_document(self, doc_id: str, data: Dict[str, Any], merge: bool = False):
        """ドキュメントを保存"""
        self.get_collection().document(doc_id).set(data, merge=merge)
    
    def update_document(self, doc_id: str, data: Dict[str, Any]):
        """ドキュメントを更新"""
        self.get_collection().document(doc_id).update(data)
    
    def delete_document(self, doc_id: str):
        """ドキュメントを削除"""
        self.get_collection().document(doc_id).delete()
    
    # ========================================
    # クエリ操作
    # ========================================
    
    def query_by_status(
        self,
        status_field: str,
        status_value: Any,
        limit: Optional[int] = None
    ) -> List[firestore.DocumentSnapshot]:
        """
        ステータスでクエリ
        
        Args:
            status_field: ステータスフィールド名 (例: "scriptStatus")
            status_value: ステータス値 (例: None, True, "pending")
            limit: 取得件数制限
        
        Returns:
            ドキュメントスナップショットのリスト
        """
        query = self.get_collection().where(
            filter=FieldFilter(status_field, "==", status_value)
        )
        
        if limit:
            query = query.limit(limit)
        
        return list(query.stream())
    
    def query_pending_scrape(self, limit: Optional[int] = None) -> List[firestore.DocumentSnapshot]:
        """スクレイプ待ちのドキュメントを取得"""
        # 実装例: scrapeStatus が None または "pending" のものを取得
        # 実際のロジックは要件に応じて調整
        return self.query_by_status("scrapeStatus", None, limit)
    
    def query_pending_transform(self, limit: Optional[int] = None) -> List[firestore.DocumentSnapshot]:
        """変換待ちのドキュメントを取得"""
        # scriptStatus が None のものを取得
        query = self.get_collection().where(
            filter=FieldFilter("scriptStatus", "==", None)
        ).where(
            filter=FieldFilter("scrapeStatus", "in", ["new", "updated"])
        )
        
        if limit:
            query = query.limit(limit)
        
        docs = list(query.stream())
        
        # まだ枠があれば scriptStatus == False も取得
        if limit and len(docs) < limit:
            query_false = self.get_collection().where(
                filter=FieldFilter("scriptStatus", "==", False)
            ).where(
                filter=FieldFilter("scrapeStatus", "in", ["new", "updated"])
            ).limit(limit - len(docs))
            
            docs += list(query_false.stream())
        
        # scraped_at でソート
        docs.sort(key=lambda d: (d.to_dict().get("scraped_at") or 0))
        
        return docs
    
    # ========================================
    # 保存ヘルパー (変更検出付き)
    # ========================================
    
    def save_with_hash_check(
        self,
        doc_id: str,
        new_data: Dict[str, Any],
        hash_field: str = "contentHash"
    ) -> str:
        """
        ハッシュ値で変更を検出して保存
        
        Args:
            doc_id: ドキュメントID
            new_data: 新しいデータ
            hash_field: ハッシュフィールド名
        
        Returns:
            "new" | "updated" | "nochange"
        """
        doc_ref = self.get_collection().document(doc_id)
        old_doc = doc_ref.get()
        
        # 更新時に潰したくないフィールド
        PROTECT_NONE_KEYS = {"mulmoScript", "videoUrl", "videoStatus"}
        
        if old_doc.exists:
            old = old_doc.to_dict() or {}
            old_hash = old.get(hash_field)
            new_hash = new_data.get(hash_field)
            
            if old_hash != new_hash:
                # 更新
                payload = dict(new_data)
                
                # None を送ると既存値を null にしてしまうので削る
                for k in list(payload.keys()):
                    if k in PROTECT_NONE_KEYS and payload[k] is None:
                        payload.pop(k)
                
                payload["scrapeStatus"] = "updated"
                payload["updatedAt"] = firestore.SERVER_TIMESTAMP
                payload["scriptStatus"] = None  # 再台本化トリガ
                
                doc_ref.set(payload, merge=True)
                print(f"🆕 更新検出: {new_data.get('original_url', doc_id)}")
                return "updated"
            else:
                # 変更なし
                print(f"⏩ 変更なし: {new_data.get('original_url', doc_id)}")
                return "nochange"
        else:
            # 新規
            payload = dict(new_data)
            payload["scrapeStatus"] = "new"
            payload.setdefault("scriptStatus", None)
            
            doc_ref.set(payload)
            print(f"✨ 新規記事: {new_data.get('original_url', doc_id)}")
            return "new"
    
    # ========================================
    # バッチ操作
    # ========================================
    
    def batch_delete(self, doc_ids: List[str], batch_size: int = 450):
        """
        複数ドキュメントを削除
        
        Args:
            doc_ids: ドキュメントIDのリスト
            batch_size: バッチサイズ
        """
        total = len(doc_ids)
        deleted = 0
        
        batch = self.db.batch()
        
        for i, doc_id in enumerate(doc_ids, start=1):
            doc_ref = self.get_collection().document(doc_id)
            batch.delete(doc_ref)
            
            if i % batch_size == 0:
                batch.commit()
                deleted += batch_size
                print(f"[BATCH DELETE] コミット: {deleted}/{total}")
                batch = self.db.batch()
        
        # 残りをコミット
        if total % batch_size != 0:
            batch.commit()
            deleted = total
        
        print(f"[BATCH DELETE] 削除完了: {deleted}/{total}")
        return deleted


# グローバルインスタンス
_firestore_client: Optional[FirestoreClient] = None


def get_firestore_client(config=None) -> FirestoreClient:
    """
    Firestoreクライアントを取得
    
    Args:
        config: Configインスタンス
    
    Returns:
        FirestoreClient インスタンス
    """
    global _firestore_client
    
    if _firestore_client is None:
        _firestore_client = FirestoreClient(config)
    
    return _firestore_client


def reload_firestore_client(config=None) -> FirestoreClient:
    """Firestoreクライアントを再初期化"""
    global _firestore_client
    _firestore_client = FirestoreClient(config)
    return _firestore_client
