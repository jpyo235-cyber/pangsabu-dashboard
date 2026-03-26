"""
팡사부 자동화 대시보드
뉴스 수집 → 스크립트 생성 → 썸네일 생성을 웹에서 한번에
"""
from flask import Flask, render_template_string, request, jsonify, send_file
import os
import json
from datetime import datetime

from news_collector import get_top_stories
from script_generator import generate_script
from thumbnail_generator import generate_thumbnail
from video_generator import generate_video

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>팡사부 자동화 대시보드</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', sans-serif;
    background: #0d0d1a;
    color: #e0e0e0;
    min-height: 100vh;
  }
  .header {
    background: linear-gradient(135deg, #1a0a2e, #2d1060);
    padding: 20px 30px;
    border-bottom: 2px solid #6a0dad;
    display: flex;
    align-items: center;
    gap: 15px;
  }
  .header h1 { font-size: 1.6rem; color: #d4a0ff; }
  .header .subtitle { font-size: 0.85rem; color: #888; }
  .container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }

  /* 단계 표시 */
  .steps {
    display: flex;
    gap: 10px;
    margin-bottom: 30px;
    flex-wrap: wrap;
  }
  .step {
    flex: 1;
    min-width: 200px;
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
    transition: border-color 0.3s;
  }
  .step.active { border-color: #6a0dad; background: #1e0a3c; }
  .step-num {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: #333;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 10px;
    font-weight: bold;
    font-size: 1rem;
  }
  .step.active .step-num { background: #6a0dad; }
  .step h3 { font-size: 0.95rem; margin-bottom: 5px; }
  .step p { font-size: 0.78rem; color: #888; }

  /* 섹션 */
  .section {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 14px;
    padding: 25px;
    margin-bottom: 25px;
  }
  .section-title {
    font-size: 1.1rem;
    font-weight: bold;
    color: #d4a0ff;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .badge {
    background: #6a0dad;
    color: white;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
  }

  /* 버튼 */
  .btn {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: bold;
    transition: all 0.2s;
  }
  .btn-primary {
    background: linear-gradient(135deg, #6a0dad, #9b30ff);
    color: white;
  }
  .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(106,13,173,0.4); }
  .btn-secondary {
    background: #2a2a4a;
    color: #ccc;
    border: 1px solid #444;
  }
  .btn-secondary:hover { background: #3a3a5a; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  /* 뉴스 카드 */
  .news-grid { display: grid; gap: 12px; }
  .news-card {
    background: #12122a;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 15px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .news-card:hover { border-color: #6a0dad; background: #1a0a3c; }
  .news-card.selected { border-color: #9b30ff; background: #1e0a3c; }
  .news-rank {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #2a2a4a;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem;
    font-weight: bold;
    flex-shrink: 0;
    color: #aaa;
  }
  .news-card.selected .news-rank { background: #6a0dad; color: white; }
  .news-title { font-size: 0.92rem; font-weight: bold; margin-bottom: 5px; }
  .news-meta { font-size: 0.75rem; color: #888; }
  .news-keywords { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px; }
  .keyword-tag {
    background: #2a2a4a;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 0.7rem;
    color: #aaa;
  }

  /* 스크립트 영역 */
  .script-tabs { display: flex; gap: 10px; margin-bottom: 15px; }
  .tab-btn {
    padding: 8px 18px;
    border: 1px solid #333;
    border-radius: 6px;
    background: #12122a;
    color: #888;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.2s;
  }
  .tab-btn.active { background: #6a0dad; color: white; border-color: #6a0dad; }
  .script-box {
    background: #0d0d1a;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 15px;
    min-height: 150px;
    font-size: 0.9rem;
    line-height: 1.7;
    white-space: pre-wrap;
    color: #ddd;
  }
  textarea.script-box {
    width: 100%;
    resize: vertical;
    font-family: inherit;
    outline: none;
  }
  textarea.script-box:focus { border-color: #6a0dad; }

  /* 썸네일 영역 */
  .thumb-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
  .input-group label { display: block; font-size: 0.82rem; color: #aaa; margin-bottom: 6px; }
  .input-group input {
    width: 100%;
    background: #0d0d1a;
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    padding: 10px 12px;
    color: #ddd;
    font-size: 0.9rem;
    outline: none;
  }
  .input-group input:focus { border-color: #6a0dad; }
  .thumb-preview { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; }
  .thumb-item { text-align: center; }
  .thumb-item img {
    width: 100%;
    border-radius: 8px;
    border: 1px solid #2a2a4a;
  }
  .thumb-item p { font-size: 0.8rem; color: #888; margin-top: 8px; }
  .thumb-item a {
    display: inline-block;
    margin-top: 8px;
    padding: 6px 14px;
    background: #2a2a4a;
    border-radius: 6px;
    color: #aaa;
    text-decoration: none;
    font-size: 0.8rem;
  }
  .thumb-item a:hover { background: #3a3a5a; color: white; }

  /* 로딩 */
  .loading {
    display: none;
    text-align: center;
    padding: 20px;
    color: #888;
  }
  .spinner {
    display: inline-block;
    width: 24px; height: 24px;
    border: 3px solid #333;
    border-top-color: #9b30ff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-right: 10px;
    vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* 태그 */
  .tags-box { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .tag {
    background: #1e0a3c;
    border: 1px solid #6a0dad;
    border-radius: 4px;
    padding: 3px 9px;
    font-size: 0.75rem;
    color: #d4a0ff;
  }

  /* 알림 */
  .toast {
    position: fixed;
    bottom: 30px;
    right: 30px;
    background: #1e0a3c;
    border: 1px solid #6a0dad;
    border-radius: 10px;
    padding: 14px 20px;
    color: #d4a0ff;
    font-size: 0.9rem;
    display: none;
    z-index: 1000;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }

  .divider { border: none; border-top: 1px solid #2a2a4a; margin: 20px 0; }
  .action-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .hint { font-size: 0.78rem; color: #666; margin-top: 8px; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🐾 팡사부 자동화 대시보드</h1>
    <div class="subtitle">뉴스 수집 → 스크립트 생성 → 썸네일 생성 자동화</div>
  </div>
</div>

<div class="container">

  <!-- 단계 안내 -->
  <div class="steps">
    <div class="step active" id="step1-indicator">
      <div class="step-num">1</div>
      <h3>뉴스 수집</h3>
      <p>오늘의 소재 자동 수집</p>
    </div>
    <div class="step" id="step2-indicator">
      <div class="step-num">2</div>
      <h3>스크립트 생성</h3>
      <p>팡사부 스타일로 자동 작성</p>
    </div>
    <div class="step" id="step3-indicator">
      <div class="step-num">3</div>
      <h3>썸네일 생성</h3>
      <p>팡사부 + 텍스트 자동 합성</p>
    </div>
  </div>

  <!-- STEP 1: 뉴스 수집 -->
  <div class="section" id="section-news">
    <div class="section-title">
      <span>📰 오늘의 소재</span>
      <span class="badge">STEP 1</span>
    </div>
    <div class="action-row">
      <button class="btn btn-primary" onclick="fetchNews()">🔄 뉴스 수집하기</button>
      <span class="hint">트럼프, 지정학, 경제 관련 최신 뉴스를 자동으로 가져옵니다</span>
    </div>
    <div class="loading" id="news-loading">
      <span class="spinner"></span>뉴스 수집 중...
    </div>
    <div id="news-list" style="margin-top:15px;"></div>
  </div>

  <!-- STEP 2: 스크립트 생성 -->
  <div class="section" id="section-script">
    <div class="section-title">
      <span>✍️ 스크립트 생성</span>
      <span class="badge">STEP 2</span>
    </div>
    <div class="action-row">
      <button class="btn btn-primary" onclick="generateScript()" id="script-btn" disabled>
        🤖 팡사부 스크립트 생성
      </button>
      <span class="hint">소재를 선택한 후 클릭하세요</span>
    </div>
    <div class="loading" id="script-loading">
      <span class="spinner"></span>팡사부 스타일로 스크립트 작성 중...
    </div>
    <div id="script-result" style="display:none; margin-top:15px;">
      <div class="script-tabs">
        <button class="tab-btn active" onclick="switchTab('korean')">🇰🇷 한국어 (닥스삼부자)</button>
        <button class="tab-btn" onclick="switchTab('english')">🌍 영어 (DrPangPsych)</button>
        <button class="tab-btn" onclick="switchTab('tags')">🏷️ 태그</button>
      </div>
      <div id="tab-korean">
        <textarea class="script-box" id="script-ko" rows="8"></textarea>
      </div>
      <div id="tab-english" style="display:none;">
        <textarea class="script-box" id="script-en" rows="8"></textarea>
      </div>
      <div id="tab-tags" style="display:none;">
        <div class="tags-box" id="tags-box"></div>
      </div>
      <hr class="divider">
      <div class="action-row" style="margin-top:10px;">
        <button class="btn btn-secondary" onclick="copyScript('ko')">📋 한국어 복사</button>
        <button class="btn btn-secondary" onclick="copyScript('en')">📋 영어 복사</button>
      </div>
    </div>
  </div>

  <!-- STEP 3: 썸네일 생성 -->
  <div class="section" id="section-thumb">
    <div class="section-title">
      <span>🖼️ 썸네일 생성</span>
      <span class="badge">STEP 3</span>
    </div>
    <div class="thumb-inputs">
      <div class="input-group">
        <label>한국어 텍스트 (10자 이내)</label>
        <input type="text" id="thumb-ko" placeholder="예: 트럼프의 덫" maxlength="12">
      </div>
      <div class="input-group">
        <label>영어 텍스트 (3~4 words)</label>
        <input type="text" id="thumb-en" placeholder="예: TRUMP'S TRAP" maxlength="25">
      </div>
    </div>
    <div class="action-row">
      <button class="btn btn-primary" onclick="generateThumbnail()">🎨 썸네일 생성</button>
      <span class="hint">스크립트 생성 후 자동으로 텍스트가 채워집니다</span>
    </div>
    <div class="loading" id="thumb-loading">
      <span class="spinner"></span>썸네일 생성 중...
    </div>
    <div class="thumb-preview" id="thumb-preview" style="display:none;"></div>
  </div>

  <!-- STEP 4: 영상 생성 -->
  <div class="section" id="section-video">
    <div class="section-title">
      <span>🎬 영상 생성</span>
      <span class="badge">STEP 4</span>
    </div>
    <div class="action-row">
      <button class="btn btn-primary" onclick="generateVideo('korean')" id="video-ko-btn" disabled>
        🇰🇷 한국어 영상 생성
      </button>
      <button class="btn btn-primary" onclick="generateVideo('english')" id="video-en-btn" disabled>
        🌍 영어 영상 생성
      </button>
      <span class="hint">스크립트 생성 후 활성화됩니다 · 약 30~60초 소요</span>
    </div>
    <div class="loading" id="video-loading">
      <span class="spinner"></span>영상 합성 중... (약 30~60초 소요)
    </div>
    <div id="video-result" style="display:none; margin-top:15px;">
      <div id="video-preview"></div>
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
let selectedNews = null;
let currentKeywords = [];

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

async function fetchNews() {
  document.getElementById('news-loading').style.display = 'block';
  document.getElementById('news-list').innerHTML = '';
  
  try {
    const res = await fetch('/api/news');
    const data = await res.json();
    
    document.getElementById('news-loading').style.display = 'none';
    
    if (data.error) {
      document.getElementById('news-list').innerHTML = `<p style="color:#f66">오류: ${data.error}</p>`;
      return;
    }
    
    const html = data.stories.map((s, i) => `
      <div class="news-card" id="news-${i}" onclick="selectNews(${i}, ${JSON.stringify(s).replace(/"/g, '&quot;')})">
        <div class="news-rank">${i+1}</div>
        <div>
          <div class="news-title">${s.title}</div>
          <div class="news-meta">${s.source} · ${s.published ? s.published.substring(0,16) : ''}</div>
          <div class="news-keywords">
            ${s.keywords.map(k => `<span class="keyword-tag">${k}</span>`).join('')}
          </div>
        </div>
      </div>
    `).join('');
    
    document.getElementById('news-list').innerHTML = html;
    document.getElementById('step1-indicator').classList.add('active');
    showToast('✅ 뉴스 수집 완료!');
    
  } catch(e) {
    document.getElementById('news-loading').style.display = 'none';
    document.getElementById('news-list').innerHTML = `<p style="color:#f66">연결 오류: ${e.message}</p>`;
  }
}

function selectNews(idx, story) {
  // 이전 선택 해제
  document.querySelectorAll('.news-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`news-${idx}`).classList.add('selected');
  
  selectedNews = story;
  currentKeywords = story.keywords || [];
  
  document.getElementById('script-btn').disabled = false;
  document.getElementById('step2-indicator').classList.add('active');
  showToast('✅ 소재 선택됨: ' + story.title.substring(0, 30) + '...');
}

async function generateScript() {
  if (!selectedNews) return;
  
  document.getElementById('script-loading').style.display = 'block';
  document.getElementById('script-result').style.display = 'none';
  
  try {
    const res = await fetch('/api/script', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        title: selectedNews.title,
        summary: selectedNews.summary
      })
    });
    const data = await res.json();
    
    document.getElementById('script-loading').style.display = 'none';
    
    if (data.error) {
      alert('오류: ' + data.error);
      return;
    }
    
    document.getElementById('script-ko').value = data.korean || data.raw;
    document.getElementById('script-en').value = data.english || '';
    
    // 태그 표시
    const tagsHtml = (data.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
    document.getElementById('tags-box').innerHTML = tagsHtml;
    
    // 썸네일 텍스트 자동 채우기
    if (data.thumbnail_ko) document.getElementById('thumb-ko').value = data.thumbnail_ko;
    if (data.thumbnail_en) document.getElementById('thumb-en').value = data.thumbnail_en;
    
    document.getElementById('script-result').style.display = 'block';
    document.getElementById('step2-indicator').classList.add('active');
    showToast('✅ 스크립트 생성 완료!');
    
  } catch(e) {
    document.getElementById('script-loading').style.display = 'none';
    alert('오류: ' + e.message);
  }
}

function switchTab(tab) {
  ['korean', 'english', 'tags'].forEach(t => {
    document.getElementById(`tab-${t}`).style.display = t === tab ? 'block' : 'none';
  });
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', ['korean','english','tags'][i] === tab);
  });
}

function copyScript(lang) {
  const el = document.getElementById(`script-${lang}`);
  el.select();
  document.execCommand('copy');
  showToast('📋 클립보드에 복사됨!');
}

async function generateThumbnail() {
  const ko = document.getElementById('thumb-ko').value.trim();
  const en = document.getElementById('thumb-en').value.trim();
  
  if (!ko || !en) {
    alert('한국어와 영어 텍스트를 모두 입력해주세요.');
    return;
  }
  
  document.getElementById('thumb-loading').style.display = 'block';
  document.getElementById('thumb-preview').style.display = 'none';
  
  try {
    const res = await fetch('/api/thumbnail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        text_ko: ko,
        text_en: en,
        keywords: currentKeywords
      })
    });
    const data = await res.json();
    
    document.getElementById('thumb-loading').style.display = 'none';
    
    if (data.error) {
      alert('오류: ' + data.error);
      return;
    }
    
    const preview = document.getElementById('thumb-preview');
    preview.innerHTML = `
      <div class="thumb-item">
        <img src="/thumbnail/${data.korean_file}" alt="한국어 썸네일">
        <p>🇰🇷 닥스삼부자 (한국어)</p>
        <a href="/thumbnail/${data.korean_file}" download>⬇️ 다운로드</a>
      </div>
      <div class="thumb-item">
        <img src="/thumbnail/${data.english_file}" alt="영어 썸네일">
        <p>🌍 DrPangPsych (영어)</p>
        <a href="/thumbnail/${data.english_file}" download>⬇️ 다운로드</a>
      </div>
    `;
    preview.style.display = 'grid';
    document.getElementById('step3-indicator').classList.add('active');
    // 영상 생성 버튼 활성화
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    showToast('✅ 썸네일 생성 완료!');
    
  } catch(e) {
    document.getElementById('thumb-loading').style.display = 'none';
    alert('오류: ' + e.message);
  }
}

let currentScriptKo = '';
let currentScriptEn = '';

async function generateVideo(channel) {
  const ko = document.getElementById('script-ko') ? document.getElementById('script-ko').value : currentScriptKo;
  const en = document.getElementById('script-en') ? document.getElementById('script-en').value : currentScriptEn;
  
  if (!ko && !en) {
    alert('먼저 스크립트를 생성해주세요.');
    return;
  }
  
  document.getElementById('video-loading').style.display = 'block';
  document.getElementById('video-result').style.display = 'none';
  document.getElementById('video-ko-btn').disabled = true;
  document.getElementById('video-en-btn').disabled = true;
  
  try {
    const res = await fetch('/api/video', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        script_ko: ko,
        script_en: en,
        keywords: currentKeywords,
        channel: channel
      })
    });
    const data = await res.json();
    
    document.getElementById('video-loading').style.display = 'none';
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    
    if (data.error) {
      alert('오류: ' + data.error);
      return;
    }
    
    const label = channel === 'korean' ? '🇰🇷 한국어 (닥스삼부자)' : '🌍 영어 (DrPangPsych)';
    const preview = document.getElementById('video-preview');
    preview.innerHTML = `
      <div style="text-align:center;">
        <video controls style="width:100%;max-width:400px;border-radius:12px;border:1px solid #2a2a4a;">
          <source src="/video/${data.video_file}" type="video/mp4">
        </video>
        <p style="margin-top:10px;font-size:0.85rem;color:#888;">${label} · ${data.duration.toFixed(0)}초</p>
        <a href="/video/${data.video_file}" download
           style="display:inline-block;margin-top:10px;padding:10px 20px;background:#2a2a4a;border-radius:8px;color:#ccc;text-decoration:none;font-size:0.85rem;">
          ⬇️ 영상 다운로드
        </a>
      </div>
    `;
    document.getElementById('video-result').style.display = 'block';
    showToast('✅ 영상 생성 완료! ' + data.duration.toFixed(0) + '초');
    
  } catch(e) {
    document.getElementById('video-loading').style.display = 'none';
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    alert('오류: ' + e.message);
  }
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/news")
def api_news():
    try:
        stories = get_top_stories(8)
        return jsonify({"stories": stories})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/script", methods=["POST"])
def api_script():
    try:
        data = request.get_json()
        title = data.get("title", "")
        summary = data.get("summary", "")
        result = generate_script(title, summary)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/thumbnail", methods=["POST"])
def api_thumbnail():
    try:
        data = request.get_json()
        text_ko = data.get("text_ko", "")
        text_en = data.get("text_en", "")
        keywords = data.get("keywords", [])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ko_file = f"thumb_korean_{timestamp}.png"
        en_file = f"thumb_english_{timestamp}.png"
        
        ko_path = f"/home/ubuntu/pangsabu/thumbnails/{ko_file}"
        en_path = f"/home/ubuntu/pangsabu/thumbnails/{en_file}"
        
        generate_thumbnail(text_ko, text_en, keywords, ko_path, "korean")
        generate_thumbnail(text_ko, text_en, keywords, en_path, "english")
        
        return jsonify({
            "korean_file": ko_file,
            "english_file": en_file
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/thumbnail/<filename>")
def serve_thumbnail(filename):
    path = f"/home/ubuntu/pangsabu/thumbnails/{filename}"
    return send_file(path, mimetype="image/png")


@app.route("/api/video", methods=["POST"])
def api_video():
    try:
        data = request.get_json()
        script_ko = data.get("script_ko", "")
        script_en = data.get("script_en", "")
        keywords  = data.get("keywords", [])
        channel   = data.get("channel", "korean")

        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_file = f"pangsabu_{channel}_{timestamp}.mp4"
        video_path = f"/home/ubuntu/pangsabu/videos/{video_file}"

        result = generate_video(
            script_ko=script_ko,
            script_en=script_en,
            keywords=keywords,
            channel=channel,
            output_path=video_path
        )
        return jsonify({
            "video_file": video_file,
            "duration": result["duration"]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route("/video/<filename>")
def serve_video(filename):
    path = f"/home/ubuntu/pangsabu/videos/{filename}"
    return send_file(path, mimetype="video/mp4")


if __name__ == "__main__":
    os.makedirs("thumbnails", exist_ok=True)
    os.makedirs("audio", exist_ok=True)
    os.makedirs("videos", exist_ok=True)
    os.makedirs("frames", exist_ok=True)
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)
