#!/bin/bash

# OMO Platform - GCPセットアップスクリプト
# このスクリプトは、GCPプロジェクトの初期設定を行います

set -e

echo "🚀 OMO Platform - GCPセットアップ"
echo "=================================="

# 1. プロジェクトIDの確認
echo "プロジェクトID命名規則: omo-[自治体名]"
echo "例: omo-moriya, omo-tsukuba, omo-kashiwa"
echo ""
read -p "GCPプロジェクトID: " PROJECT_ID
gcloud config set project $PROJECT_ID

# プロジェクトIDから自治体名を抽出
MUNICIPALITY=$(echo $PROJECT_ID | sed 's/^omo-//')
echo ""
echo "✅ 自治体名: $MUNICIPALITY"
echo "   プロジェクトID: $PROJECT_ID"

# 2. 必要なAPIの有効化
echo ""
echo "📦 必要なAPIを有効化中..."
gcloud services enable \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  generativelanguage.googleapis.com

echo "✅ API有効化完了"

# 3. Firestoreの初期化
echo ""
echo "🔥 Firestoreを初期化中..."
echo "注: Firestoreが既に初期化されている場合はスキップされます"
gcloud firestore databases create --location=asia-northeast1 --type=firestore-native || echo "Firestore already initialized"

# 4. Gemini APIキーの発行
echo ""
echo "🔑 Gemini APIキーを発行中..."

# APIキーを自動発行
API_KEY_NAME="gemini-api-key-$(date +%s)"
GOOGLE_API_KEY=$(gcloud alpha services api-keys create $API_KEY_NAME \
  --display-name="Gemini API Key for OMO Platform" \
  --api-target=service=generativelanguage.googleapis.com \
  --format="value(keyString)" 2>/dev/null)

# APIキー発行に失敗した場合は手動入力
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "⚠️ 自動発行に失敗しました。手動で入力してください。"
  echo ""
  echo "APIキーの発行方法:"
  echo "  1. Google AI Studio: https://aistudio.google.com/app/apikey"
  echo "  2. GCPコンソール: https://console.cloud.google.com/apis/credentials"
  echo ""
  read -p "Google API Key (Gemini用): " GOOGLE_API_KEY
else
  echo "✅ APIキーを自動発行しました"
  echo "   APIキー名: $API_KEY_NAME"
  echo "   APIキー: ${GOOGLE_API_KEY:0:20}..."
fi

# Secret Managerに保存
echo ""
echo "🔐 Secret Managerにシークレットを保存中..."
echo -n "$GOOGLE_API_KEY" | gcloud secrets create google-api-key --data-file=- || \
  echo -n "$GOOGLE_API_KEY" | gcloud secrets versions add google-api-key --data-file=-

echo "✅ Google API Keyを保存しました"

# 5. カスタムサービスアカウントの作成
echo ""
echo "👤 カスタムサービスアカウントを作成中..."

# サービスアカウント名を自動設定
DEFAULT_SA_NAME="omo-${MUNICIPALITY}-sa"
read -p "サービスアカウント名 [${DEFAULT_SA_NAME}]: " SA_NAME
SA_NAME=${SA_NAME:-$DEFAULT_SA_NAME}

# サービスアカウントのメールアドレス
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# サービスアカウントを作成
gcloud iam service-accounts create $SA_NAME \
  --display-name="OMO Platform Service Account for ${MUNICIPALITY}" \
  --description="Service account for OMO Platform - ${MUNICIPALITY}" || echo "Service account already exists"

echo "✅ サービスアカウント作成: $SA_EMAIL"

# 6. サービスアカウントに権限を付与
echo ""
echo "🔑 サービスアカウントに権限を付与中..."

# Firestore User (データの読み書き)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"

# Secret Manager Secret Accessor (シークレットの読み取り)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Vertex AI User (Gemini APIの使用)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# Cloud Storage Object Admin (ストレージへのアクセス)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

# Logs Writer (ログの書き込み)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"

echo "✅ 権限付与完了"

# 7. Cloud Buildにサービスアカウントの使用を許可
echo ""
echo "🔨 Cloud Buildの設定中..."

# Cloud BuildサービスアカウントにService Account User権限を付与
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"

echo "✅ Cloud Buildがカスタムサービスアカウントを使用できるようになりました"

# 8. Cloud Run APIを有効化
echo ""
echo "📦 Cloud Run APIを有効化中..."
gcloud services enable run.googleapis.com

# 9. Dockerイメージのビルドとpush
echo ""
echo "🐳 Dockerイメージをビルド中..."
echo "   自治体名: $MUNICIPALITY"

IMAGE_NAME="gcr.io/${PROJECT_ID}/omo-${MUNICIPALITY}"

gcloud builds submit --tag $IMAGE_NAME

echo "✅ Dockerイメージをビルドしました: $IMAGE_NAME"

# 10. Cloud Run Jobsを作成
echo ""
echo "🏃 Cloud Run Jobsを作成中..."

JOB_NAME="omo-${MUNICIPALITY}-job"

gcloud run jobs create $JOB_NAME \
  --image $IMAGE_NAME \
  --region asia-northeast1 \
  --service-account $SA_EMAIL \
  --set-env-vars MUNICIPALITY=$MUNICIPALITY,FIRESTORE_PROJECT_ID=$PROJECT_ID,GEMINI_MODEL_NAME=gemini-2.5-flash,PYTHONPATH=/app \
  --set-secrets GOOGLE_API_KEY=google-api-key:latest \
  --max-retries 1 \
  --task-timeout 3600 \
  --memory 2Gi \
  --cpu 2 || echo "Job already exists"

echo "✅ Cloud Run Jobsを作成しました: $JOB_NAME"

# 11. Cloud Schedulerの設定(オプション)
echo ""
read -p "Cloud Schedulerで定期実行を設定しますか? (y/N): " SETUP_SCHEDULER

if [[ "$SETUP_SCHEDULER" =~ ^[Yy]$ ]]; then
  echo ""
  echo "⏰ Cloud Schedulerを設定中..."
  
  # Cloud Scheduler APIを有効化
  gcloud services enable cloudscheduler.googleapis.com
  
  # スケジュールを入力
  echo "スケジュール例:"
  echo "  毎日9:00: 0 9 * * *"
  echo "  平日9:00: 0 9 * * 1-5"
  echo "  6時間ごと: 0 */6 * * *"
  read -p "スケジュール (cron形式) [0 9 * * *]: " SCHEDULE
  SCHEDULE=${SCHEDULE:-"0 9 * * *"}
  
  # Cloud Schedulerジョブを作成
  SCHEDULER_NAME="omo-${MUNICIPALITY}-daily"
  
  gcloud scheduler jobs create http $SCHEDULER_NAME \
    --location=asia-northeast1 \
    --schedule="$SCHEDULE" \
    --time-zone="Asia/Tokyo" \
    --uri="https://asia-northeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email=$SA_EMAIL \
    --description="OMO Platform daily scrape and transform for ${MUNICIPALITY}" || echo "Scheduler job already exists"
  
  echo "✅ Cloud Schedulerを設定しました: $SCHEDULER_NAME"
  echo "   スケジュール: $SCHEDULE (Asia/Tokyo)"
else
  echo "⏭️  Cloud Schedulerの設定をスキップしました"
  echo "   手動実行: gcloud run jobs execute $JOB_NAME --region asia-northeast1"
fi

echo ""
echo "✅ セットアップ完了!"
echo ""
echo "リソース一覧:"
echo "  - プロジェクト: $PROJECT_ID"
echo "  - 自治体: $MUNICIPALITY"
echo "  - サービスアカウント: $SA_EMAIL"
echo "  - Dockerイメージ: $IMAGE_NAME"
echo "  - Cloud Run Job: $JOB_NAME"
if [[ "$SETUP_SCHEDULER" =~ ^[Yy]$ ]]; then
  echo "  - Cloud Scheduler: $SCHEDULER_NAME"
fi
echo ""
echo "次のステップ:"
echo "1. 手動でジョブを実行してテスト:"
echo "   gcloud run jobs execute $JOB_NAME --region asia-northeast1"
echo ""
echo "2. ジョブの実行履歴を確認:"
echo "   https://console.cloud.google.com/run/jobs/details/asia-northeast1/$JOB_NAME"
echo ""
if [[ "$SETUP_SCHEDULER" =~ ^[Yy]$ ]]; then
  echo "3. Cloud Schedulerの管理:"
  echo "   https://console.cloud.google.com/cloudscheduler"
  echo ""
fi
