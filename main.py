#main.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path
import uuid

from compressor import compress_image, DEFAULT_MAX_SIZE, DEFAULT_JPEG_QUALITY

app = FastAPI(title="VRChat Image Compressor API")

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#6枚目より以前のファイルを削除
from pathlib import Path
import os
# 既存の import に続けて OK

MAX_STATIC_FILES = 5  # 5枚まで

def cleanup_static_dir():
    """static フォルダ内に MAX_STATIC_FILES より多くファイルがあれば、中身を全部削除する。"""
    if not STATIC_DIR.exists():
        return

    files = [p for p in STATIC_DIR.iterdir() if p.is_file()]
    if len(files) <= MAX_STATIC_FILES:
        return

    # 要件：5枚溜まったら static の中身を削除
    for f in files:
        try:
            f.unlink()
        except Exception:
            pass

#TMP掃除ロジック
from datetime import datetime, timedelta  # 追加
import time

TEMP_DIR = Path("tmp")
TEMP_DIR.mkdir(exist_ok=True)

TMP_EXPIRE_HOURS = 1  # 例: 1時間より古いものを削除

def cleanup_tmp_dir():
    """tmp フォルダ内で、TMP_EXPIRE_HOURS より古いファイルを削除する。"""
    if not TEMP_DIR.exists():
        return

    now = time.time()
    expire_sec = TMP_EXPIRE_HOURS * 3600

    for p in TEMP_DIR.iterdir():
        if not p.is_file():
            continue
        try:
            mtime = p.stat().st_mtime
            if now - mtime > expire_sec:
                p.unlink()
        except Exception:
            # ログを入れたければここで print や logging
            pass


# --- フロントエンド（トップページ） ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>VRChat Image Compressor</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #111827; color: #e5e7eb; margin: 0; padding: 0; }
    .container { max-width: 720px; margin: 40px auto; padding: 24px;
                 background: #1f2937; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,.35); }
    h1 { margin-top: 0; font-size: 24px; color: #bfdbfe; }
    p.desc { color: #9ca3af; font-size: 14px; }
    label { font-size: 14px; display: block; margin-bottom: 6px; }
    input[type="file"] { margin: 8px 0 16px; }
    .row { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
    .row input[type="number"] { width: 100px; padding: 4px 6px;
                                background: #111827; border: 1px solid #4b5563;
                                border-radius: 6px; color: #e5e7eb; }
    button { background: #3b82f6; border: none; color: white; padding: 8px 16px;
             border-radius: 9999px; cursor: pointer; font-size: 14px; }
    button:disabled { background: #4b5563; cursor: default; }
    .result { margin-top: 20px; padding: 12px; border-radius: 8px; background: #030712; font-size: 13px; }
    .url-box { display: flex; margin-top: 8px; }
    .url-box input { flex: 1; padding: 6px 8px; font-size: 12px;
                     border-radius: 6px 0 0 6px; border: 1px solid #374151;
                     background: #111827; color: #e5e7eb; }
    .url-box button { border-radius: 0 6px 6px 0; }
    .small { font-size: 12px; color: #9ca3af; }
    .error { color: #fecaca; }
    .preview { margin-top: 12px; max-height: 240px; }
    .preview img { max-width: 100%; max-height: 240px; border-radius: 8px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>VRChat Image Compressor</h1>
    <p class="desc">
      画像をアップロードして VRChat の ImagePad などから読み込めるURLを生成します。
      （ローカル環境では <code>http://127.0.0.1:8000</code> のみからアクセス可能です）
    </p>

    <label for="file">画像ファイル</label>
    <input id="file" type="file" accept="image/*" />

    <div class="row">
      <div>
        <label for="max_size">最大サイズ（長辺, px）</label>
        <input id="max_size" type="number" value="1024" min="64" max="4096" />
      </div>
      <div>
        <label for="quality">JPEG品質</label>
        <input id="quality" type="number" value="85" min="10" max="95" />
      </div>
    </div>

    <button id="upload_btn">アップロード＆圧縮</button>

    <div id="result" class="result" style="display:none;"></div>
  </div>

  <script>
    const uploadBtn = document.getElementById("upload_btn");
    const fileInput = document.getElementById("file");
    const maxSizeInput = document.getElementById("max_size");
    const qualityInput = document.getElementById("quality");
    const resultDiv = document.getElementById("result");

    uploadBtn.addEventListener("click", async () => {
      const file = fileInput.files[0];
      if (!file) {
        alert("画像ファイルを選択してください。");
        return;
      }

      const maxSize = maxSizeInput.value || "1024";
      const quality = qualityInput.value || "85";

      const formData = new FormData();
      formData.append("file", file);
      formData.append("max_size", maxSize);
      formData.append("quality", quality);

      uploadBtn.disabled = true;
      uploadBtn.textContent = "アップロード中...";

      try {
        const res = await fetch("/upload", {
          method: "POST",
          body: formData,
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "アップロードに失敗しました");
        }

        const fullUrl = window.location.origin + data.image_url;

        resultDiv.style.display = "block";
        resultDiv.innerHTML = `
          <div>圧縮が完了しました。</div>
          <div class="small">このURLを VRChat の ImagePad / 画像ローダーに貼り付けてください。</div>
          <div class="url-box" style="margin-top:8px;">
            <input id="url_field" type="text" value="${fullUrl}" readonly />
            <button id="copy_btn">コピー</button>
          </div>
          <div class="preview">
            <img src="${fullUrl}" alt="preview" />
          </div>
        `;

        const copyBtn = document.getElementById("copy_btn");
        const urlField = document.getElementById("url_field");
        copyBtn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(urlField.value);
            copyBtn.textContent = "コピーしました";
            setTimeout(() => (copyBtn.textContent = "コピー"), 1500);
          } catch (e) {
            alert("クリップボードへのコピーに失敗しました: " + e);
          }
        });

      } catch (e) {
        resultDiv.style.display = "block";
        resultDiv.innerHTML = `<div class="error">エラー: ${e}</div>`;
      } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = "アップロード＆圧縮";
      }
    });
  </script>
</body>
</html>
    """
# --- ここに前回の /upload エンドポイントをそのまま置く ---
@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    max_size: int = Form(DEFAULT_MAX_SIZE),
    quality: int = Form(DEFAULT_JPEG_QUALITY),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="画像ファイルを送信してください。")

    # ★ tmp の古いファイルを掃除
    cleanup_tmp_dir()

    # 一時ファイルに保存
    temp_dir = TEMP_DIR
    temp_dir.mkdir(exist_ok=True)
    suffix = Path(file.filename).suffix
    temp_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = temp_dir / temp_name

    with temp_path.open("wb") as f:
        f.write(await file.read())

    try:
        out_dir = STATIC_DIR
        out_path = compress_image(temp_path, out_dir, max_size=max_size, quality=quality)
        cleanup_static_dir()  # ここは前に実装した通り
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"圧縮に失敗しました: {e}")
    finally:
        temp_path.unlink(missing_ok=True)

    image_url = f"/static/{out_path.name}"

    return {
        "image_url": image_url,
        "filename": out_path.name,
        "max_size": max_size,
        "quality": quality,
    }
