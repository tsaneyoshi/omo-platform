FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 依存関係をインストール
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY backend/ ./backend/
COPY config/ ./config/
COPY assets/ ./assets/

# 環境変数を設定
ENV PYTHONPATH=/app

# エントリーポイントスクリプトを作成
RUN echo '#!/bin/bash\n\
set -e\n\
echo "🚀 OMO Platform - Starting..."\n\
echo "Municipality: $MUNICIPALITY"\n\
echo ""\n\
echo "📥 Step 1: Scraping..."\n\
python backend/scrape/main.py\n\
echo ""\n\
echo "🔄 Step 2: Transforming..."\n\
python backend/transform/main.py\n\
echo ""\n\
echo "✅ Completed!"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# エントリーポイントを設定
ENTRYPOINT ["/app/entrypoint.sh"]
