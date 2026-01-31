import os
import datetime
import json
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- 設定 ---
# GitHub Secretsから環境変数を取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FIREBASE_SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT")

# Firebase初期化
if not firebase_admin._apps:
    cred_dict = json.loads(FIREBASE_SERVICE_ACCOUNT)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_daily_theme():
    """今日のテーマを取得または生成する"""
    today = datetime.date.today().isoformat()
    theme_ref = db.collection('daily_themes').document(today)
    doc = theme_ref.get()

    if doc.exists:
        return doc.to_dict()['theme']
    else:
        # テーマがなければGeminiに考えてもらう
        prompt = "今日のnote記事のための興味深いブログテーマを1つだけ出力してください（例：最新AI技術、節約術など）"
        response = model.generate_content(prompt)
        new_theme = response.text.strip()
        theme_ref.set({'theme': new_theme, 'created_at': firestore.SERVER_TIMESTAMP})
        return new_theme

def generate_articles(theme, count=5):
    """テーマに沿って重複しない記事を生成して保存する"""
    articles_ref = db.collection('articles')
    
    generated_count = 0
    while generated_count < count:
        prompt = f"テーマ「{theme}」に基づいた、note用の記事を1つ作成してください。記事生成以外の挨拶、雑談、会話は不要です。以下のJSON形式で出力してください：\n" \
                 "{\"title\": \"タイトル\", \"content\": \"本文\", \"tags\": [\"タグ1\", \"タグ2\"]}"
        
        try:
            response = model.generate_content(prompt)
            # JSON部分を抽出（GeminiがMarkdown記法で返す場合があるため）
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            
            # 重複チェック（タイトルで判定）
            existing = articles_ref.where('title', '==', data['title']).get()
            if not existing:
                data['theme'] = theme
                data['created_at'] = firestore.SERVER_TIMESTAMP
                articles_ref.add(data)
                generated_count += 1
                print(f"Saved: {data['title']}")
            else:
                print(f"Duplicate found: {data['title']}, retrying...")
                
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    theme = get_daily_theme()
    print(f"Today's Theme: {theme}")
    generate_articles(theme)
