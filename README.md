# OMO Platform

お知らせが会いに来るまち

自治体の情報を市民に届けるオープンソースプラットフォーム

---

## 🌟 コンセプト

情報は"届けに行く"もの。市民がいつも使っている場所に、わかりやすい形で運んでいく。

### 特徴

- 🌐 **マルチソース**: 自治体HPなど複数の情報源に対応
- 🔄 **マルチフォーマット**: テキスト、画像、動画に自動変換
- 🔓 **オープンソース**: 他の自治体でも利用可能な設計

---

## 🏗️ アーキテクチャ

```
情報源泉 → 変換 → 配信
  ↓        ↓      ↓
scrape  transform delivery
```

### 情報源 (Scrape)
- 自治体公式HP

### 変換 (Transform)
- **簡潔テキスト**: 3行でわかる要約
- **1枚絵**: 視覚的に伝わる画像
- **ショート動画**: 15-60秒 (YouTube Shorts, Instagram Reels向け)

---

## 🚀 クイックスタート

### 1. セットアップ

```bash
cd /Users/saneyoshi/Desktop/omo-platform

# ディレクトリ構造を作成
bash scripts/setup.sh

# 依存関係をインストール
cd backend
pip install -r requirements.txt
```

### 2. 設定ファイルの作成

```bash
# 環境変数
cp config/.env.example config/.env
# .envを編集してAPIキーなどを設定

# 自治体設定
cp config/municipalities/template.yaml config/municipalities/your_city.yaml
# your_city.yamlを編集
```

### 3. ローカル実行

```bash
# スクレイプ
cd backend/scrape
python main.py

# 変換
cd backend/transform
python main.py

# 配信
cd backend/delivery
python main.py
```

### 4. GCPデプロイ

```bash
# Cloud Functionsにデプロイ
bash scripts/deploy.sh
```

---

## 📁 プロジェクト構造

```
omo-platform/
├── backend/              # バックエンド (Python)
│   ├── scrape/          # 情報収集
│   ├── transform/       # コンテンツ変換
│   ├── delivery/        # 配信
│   ├── common/          # 共通ライブラリ
│   └── api/             # Cloud Functions
│
├── frontend/            # フロントエンド (将来用)
│
├── config/              # 設定ファイル
│   ├── municipalities/  # 自治体ごとの設定
│   └── secrets/         # 秘密情報 (.gitignore)
│
├── docs/                # ドキュメント
│
└── scripts/             # ユーティリティスクリプト
```

---

## 🔧 他の自治体での利用方法

### 1. 自治体設定ファイルを作成

```yaml
# config/municipalities/your_city.yaml
municipality:
  name: "あなたの市"
  prefecture: "都道府県"
  character: "マスコットキャラクター名"

sources:
  municipal_hp:
    enabled: true
    scraper: "your_city"
    url: "https://www.city.example.jp/"
```

### 2. スクレイパーを実装

```python
# backend/scrape/sources/municipal/your_city.py
from .base import MunicipalScraper

class YourCityScraper(MunicipalScraper):
    def get_news_list(self):
        # あなたの自治体のHTML構造に合わせて実装
        pass
```

### 3. 環境変数を設定

```bash
export MUNICIPALITY=your_city
```

詳細は [docs/configuration.md](docs/configuration.md) を参照してください。

---

## 📄 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照してください。

---

**お知らせが会いに来るまち、始めましょう。**
