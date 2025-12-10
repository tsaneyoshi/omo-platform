# -*- coding: utf-8 -*-
"""
OMO Platform - ストレージ操作

Cloud Storage (GCS) またはローカルファイルシステムへの保存を担当
"""

import os
from pathlib import Path
from typing import Optional
from google.cloud import storage
from backend.common.config import get_config

# ローカル保存先 (エミュレータ用)
LOCAL_STORAGE_DIR = Path(__file__).parent.parent.parent / "storage"

def get_storage_client():
    """GCSクライアントを取得"""
    return storage.Client()

def save_file(data: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """
    ファイルを保存する
    
    Args:
        data: ファイルデータ (bytes)
        filename: 保存ファイル名 (例: "images/foo.png")
        content_type: MIMEタイプ
    
    Returns:
        保存先パス (gs://... または local://...)
    """
    config = get_config()
    
    # エミュレータ環境、またはデバッグモードでGCSバケット未設定の場合はローカル保存
    if os.getenv("FIRESTORE_EMULATOR_HOST") or not os.getenv("GCS_BUCKET_NAME"):
        return _save_local(data, filename)
    else:
        return _save_gcs(data, filename, content_type, os.getenv("GCS_BUCKET_NAME"))

def _save_local(data: bytes, filename: str) -> str:
    """ローカルに保存"""
    # ディレクトリ作成
    file_path = LOCAL_STORAGE_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(data)
    
    print(f"💾 ローカル保存: {file_path}")
    return f"local://{file_path}"

def _save_gcs(data: bytes, filename: str, content_type: str, bucket_name: str) -> str:
    """GCSに保存"""
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    
    blob.upload_from_string(data, content_type=content_type)
    
    print(f"☁️ GCS保存: gs://{bucket_name}/{filename}")
    return f"gs://{bucket_name}/{filename}"
