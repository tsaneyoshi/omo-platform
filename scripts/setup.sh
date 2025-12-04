#!/bin/bash

# OMO Platform セットアップスクリプト

set -e

echo "🚀 OMO Platform セットアップを開始します..."

# ディレクトリ構造を作成
echo "📁 ディレクトリ構造を作成中..."

# Backend
mkdir -p backend/scrape/core
mkdir -p backend/scrape/sources/municipal
mkdir -p backend/scrape/sources/social
mkdir -p backend/scrape/sources/schools
mkdir -p backend/transform/core
mkdir -p backend/transform/text
mkdir -p backend/transform/image
mkdir -p backend/transform/video
mkdir -p backend/transform/audio
mkdir -p backend/delivery/core
mkdir -p backend/delivery/channels
mkdir -p backend/common
mkdir -p backend/api

# Frontend (将来用)
mkdir -p frontend/src/components
mkdir -p frontend/src/pages
mkdir -p frontend/public

# Config
mkdir -p config/municipalities
mkdir -p config/secrets

# Docs
mkdir -p docs

# Scripts
mkdir -p scripts

# Assets
mkdir -p assets/images
mkdir -p assets/fonts
mkdir -p assets/templates

echo "✅ ディレクトリ構造を作成しました"

# __init__.py を作成
echo "📝 __init__.py を作成中..."

touch backend/__init__.py
touch backend/scrape/__init__.py
touch backend/scrape/core/__init__.py
touch backend/scrape/sources/__init__.py
touch backend/scrape/sources/municipal/__init__.py
touch backend/scrape/sources/social/__init__.py
touch backend/scrape/sources/schools/__init__.py
touch backend/transform/__init__.py
touch backend/transform/core/__init__.py
touch backend/transform/text/__init__.py
touch backend/transform/image/__init__.py
touch backend/transform/video/__init__.py
touch backend/transform/audio/__init__.py
touch backend/delivery/__init__.py
touch backend/delivery/core/__init__.py
touch backend/delivery/channels/__init__.py
touch backend/common/__init__.py
touch backend/api/__init__.py

echo "✅ __init__.py を作成しました"

# .env.example を作成
echo "🔐 .env.example を作成中..."

cat > config/.env.example << 'EOF'
# GCP設定
FIRESTORE_PROJECT_ID=your-project-id
FIRESTORE_DATABASE_ID=(default)
FIRESTORE_COLLECTION_NAME=omo

# Google API
GOOGLE_API_KEY=your-google-api-key

# Document AI
DOCAI_LOCATION=us
DOCAI_PROCESSOR_ID=your-processor-id

# YouTube
YOUTUBE_API_KEY=your-youtube-api-key
YOUTUBE_CHANNEL_ID=your-channel-id

# Twitter/X
TWITTER_BEARER_TOKEN=your-twitter-bearer-token
TWITTER_API_KEY=your-twitter-api-key
TWITTER_API_SECRET=your-twitter-api-secret

# LINE
LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token

# Instagram
INSTAGRAM_ACCESS_TOKEN=your-instagram-access-token

# 自治体設定
MUNICIPALITY=moriya

# デバッグ
DEBUG=true
EOF

echo "✅ .env.example を作成しました"

# テンプレート設定ファイルを作成
echo "📄 テンプレート設定ファイルを作成中..."

cat > config/municipalities/template.yaml << 'EOF'
# 自治体設定テンプレート
# このファイルをコピーして your_city.yaml を作成してください

municipality:
  name: "あなたの市"
  prefecture: "都道府県"
  character: "マスコットキャラクター名"
  
sources:
  # 自治体公式HP
  municipal_hp:
    enabled: true
    scraper: "your_city"  # sources/municipal/your_city.py を使用
    url: "https://www.city.example.jp/"
    selectors:
      list_item_container: ".news-list .item"
      date: ".date"
      link: "a"
      title: "h1.title"
      content_body: ".content"
    
  # Twitter/X
  twitter:
    enabled: false
    username: "your_city_official"
    
  # YouTube
  youtube:
    enabled: false
    channel_id: "UC..."
    
  # Instagram
  instagram:
    enabled: false
    username: "your_city_official"
    
  # 学校HP
  schools:
    enabled: false
    list: []

transform:
  # 簡潔テキスト
  text_simple:
    enabled: true
    max_chars: 150
    
  # 1枚絵
  image_single:
    enabled: true
    size: [1080, 1080]
    template: "default"
    
  # ショート動画
  video_short:
    enabled: true
    duration_max: 60
    aspect_ratio: "9:16"
    
  # 長尺動画
  video_long:
    enabled: true
    scene_min: 3
    scene_max: 8
    
  # 音声
  audio:
    enabled: false

delivery:
  # YouTube
  youtube_shorts:
    enabled: false
    privacy: "public"
    
  youtube_regular:
    enabled: false
    privacy: "public"
    
  # LINE
  line:
    enabled: false
    
  # Twitter/X
  twitter:
    enabled: false
    
  # Instagram
  instagram:
    enabled: false
    
  # Email
  email:
    enabled: false
EOF

echo "✅ テンプレート設定ファイルを作成しました"

echo ""
echo "🎉 セットアップ完了!"
echo ""
echo "次のステップ:"
echo "1. config/.env.example を config/.env にコピーして編集"
echo "2. config/municipalities/template.yaml をコピーして自治体設定を作成"
echo "3. backend/requirements.txt の依存関係をインストール"
echo "   cd backend && pip install -r requirements.txt"
echo ""
