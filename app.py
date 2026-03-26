"""
팡사부 자동화 대시보드 v2.0
뉴스 수집 → 스크립트 생성 → 썸네일 생성 → 영상 생성 → YouTube 업로드/예약
Railway 영구 서버 배포 버전
"""
from flask import Flask, render_template_string, request, jsonify, send_file
import os
import json
import threading
from datetime import datetime, timezone, timedelta

from news_collector import get_top_stories
from script_generator import generate_script
from thumbnail_generator import generate_thumbnail
from video_generator import generate_video
from youtube_uploader import (
    check_auth_status, upload_video, get_next_schedule_time,
    list_uploaded_videos, revoke_auth, start_oauth_local_server,
    get_token_as_base64, get_credentials_as_base64,
    TOKEN_FILE
)

app = Flask(__name__)

KST = timezone(timedelta(hours=9))

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
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }
  .header h1 { font-size: 1.6rem; color: #d4a0ff; }
  .header .subtitle { font-size: 0.85rem; color: #888; }
  .auth-badge {
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: bold;
    cursor: pointer;
    border: none;
  }
  .auth-badge.connected { background: #1a3a1a; color: #4caf50; border: 1px solid #4caf50; }
  .auth-badge.disconnected { background: #3a1a1a; color: #f44336; border: 1px solid #f44336; }
  .container { max-width: 1100px; margin: 0 auto; padding: 30px 20px; }

  .steps {
    display: flex;
    gap: 10px;
    margin-bottom: 30px;
    flex-wrap: wrap;
  }
  .step {
    flex: 1;
    min-width: 160px;
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 15px;
    text-align: center;
    transition: border-color 0.3s;
  }
  .step.active { border-color: #6a0dad; background: #1e0a3c; }
  .step.done { border-color: #4caf50; background: #0a2010; }
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
  .step.done .step-num { background: #4caf50; }
  .step h3 { font-size: 0.9rem; margin-bottom: 4px; }
  .step p { font-size: 0.75rem; color: #888; }

  .section {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 14px;
    padding: 25px;
    margin-bottom: 20px;
  }
  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 18px;
    font-size: 1.1rem;
    font-weight: bold;
    color: #c0a0ff;
  }
  .badge {
    background: #2a1a4a;
    color: #9060cc;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 0.75rem;
  }
  .badge.green { background: #0a2a0a; color: #4caf50; }
  .badge.red { background: #2a0a0a; color: #f44336; }
  .badge.yellow { background: #2a2a0a; color: #ffcc00; }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: bold;
    transition: opacity 0.2s, transform 0.1s;
  }
  .btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-primary { background: #6a0dad; color: white; }
  .btn-secondary { background: #2a2a4a; color: #ccc; }
  .btn-success { background: #1a5a1a; color: #4caf50; border: 1px solid #4caf50; }
  .btn-danger { background: #3a0a0a; color: #f44336; border: 1px solid #f44336; font-size: 0.8rem; }
  .btn-upload { background: linear-gradient(135deg, #c00, #900); color: white; font-size: 1rem; padding: 12px 28px; }
  .btn-copy { background: #1a2a3a; color: #4a9eff; border: 1px solid #4a9eff; font-size: 0.8rem; padding: 6px 12px; }

  .news-card {
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
    cursor: pointer;
    display: flex;
    gap: 12px;
    transition: border-color 0.2s;
  }
  .news-card:hover { border-color: #6a0dad; }
  .news-card.selected { border-color: #9060cc; background: #1a0a2e; }
  .news-rank {
    min-width: 28px; height: 28px;
    background: #2a1a4a;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: bold; color: #9060cc;
  }
  .news-title { font-size: 0.9rem; margin-bottom: 4px; }
  .news-meta { font-size: 0.75rem; color: #666; margin-bottom: 6px; }
  .news-keywords { display: flex; gap: 5px; flex-wrap: wrap; }
  .keyword-tag {
    background: #1a1a3a;
    color: #8080cc;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.72rem;
  }

  .script-tabs { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .tab-btn {
    padding: 7px 15px;
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 8px;
    color: #888;
    cursor: pointer;
    font-size: 0.82rem;
  }
  .tab-btn.active { border-color: #6a0dad; color: #d4a0ff; background: #1e0a3c; }
  .script-box {
    width: 100%;
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 12px;
    font-size: 0.88rem;
    resize: vertical;
    line-height: 1.6;
  }
  .tags-box {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
    background: #0f0f20;
    border-radius: 8px;
    min-height: 60px;
  }
  .tag {
    background: #1a1a3a;
    color: #8080cc;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
  }

  .thumb-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-bottom: 15px;
  }
  @media (max-width: 600px) { .thumb-inputs { grid-template-columns: 1fr; } }
  .input-group label { display: block; font-size: 0.82rem; color: #888; margin-bottom: 6px; }
  .input-group input, .input-group textarea {
    width: 100%;
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 10px 12px;
    font-size: 0.9rem;
  }
  .thumb-preview {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-top: 15px;
  }
  @media (max-width: 600px) { .thumb-preview { grid-template-columns: 1fr; } }
  .thumb-item {
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
  }
  .thumb-item img { width: 100%; border-radius: 8px; margin-bottom: 8px; }
  .thumb-item p { font-size: 0.82rem; color: #888; margin-bottom: 8px; }
  .thumb-item a { color: #9060cc; font-size: 0.8rem; text-decoration: none; }

  .loading {
    display: none;
    align-items: center;
    gap: 10px;
    color: #888;
    font-size: 0.88rem;
    padding: 12px 0;
  }
  .spinner {
    width: 18px; height: 18px;
    border: 2px solid #333;
    border-top-color: #6a0dad;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .upload-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-top: 15px;
  }
  @media (max-width: 700px) { .upload-grid { grid-template-columns: 1fr; } }
  .upload-card {
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 18px;
  }
  .upload-card h3 { font-size: 0.95rem; margin-bottom: 12px; color: #d4a0ff; }
  .channel-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 0.75rem;
    margin-bottom: 12px;
  }
  .channel-ko { background: #1a2a3a; color: #4a9eff; }
  .channel-en { background: #2a1a1a; color: #ff6b6b; }
  .schedule-info {
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82rem;
    color: #aaa;
    margin: 10px 0;
  }
  .schedule-info strong { color: #d4a0ff; }
  .upload-options { margin: 12px 0; }
  .upload-options label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    margin-bottom: 8px;
  }
  .upload-options input[type="radio"] { accent-color: #6a0dad; }
  .datetime-input {
    width: 100%;
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 0.85rem;
    margin-top: 8px;
  }
  .upload-result {
    background: #0a2a0a;
    border: 1px solid #4caf50;
    border-radius: 8px;
    padding: 12px;
    margin-top: 12px;
    font-size: 0.85rem;
  }
  .upload-result a { color: #4caf50; }
  .upload-result.error { background: #2a0a0a; border-color: #f44336; color: #f44336; }

  .auth-section {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }
  .auth-url-box {
    background: #0f0f20;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 12px;
    font-size: 0.78rem;
    word-break: break-all;
    color: #9060cc;
    margin: 12px 0;
    cursor: pointer;
    line-height: 1.5;
  }

  .token-export-box {
    background: #0a1a0a;
    border: 1px solid #2a4a2a;
    border-radius: 10px;
    padding: 16px;
    margin-top: 15px;
  }
  .token-export-box h4 { color: #4caf50; margin-bottom: 8px; font-size: 0.9rem; }
  .token-export-box p { font-size: 0.8rem; color: #888; margin-bottom: 10px; }
  .token-value {
    background: #0f0f20;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 10px;
    font-size: 0.72rem;
    font-family: monospace;
    color: #aaa;
    word-break: break-all;
    max-height: 80px;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .history-item {
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .history-item .title { font-size: 0.88rem; flex: 1; }
  .history-item .date { font-size: 0.75rem; color: #666; }
  .history-item a { color: #9060cc; font-size: 0.8rem; text-decoration: none; }

  .divider { border: none; border-top: 1px solid #2a2a4a; margin: 20px 0; }
  .action-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .hint { font-size: 0.78rem; color: #666; }
  .toast {
    display: none;
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: #2a1a4a;
    color: #d4a0ff;
    padding: 12px 24px;
    border-radius: 20px;
    font-size: 0.9rem;
    z-index: 999;
    border: 1px solid #6a0dad;
  }
  .video-title-input, .video-desc-input {
    width: 100%;
    background: #0f0f20;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 10px 12px;
    font-size: 0.88rem;
    margin-bottom: 8px;
  }
  .video-desc-input { resize: vertical; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🐾 팡사부 자동화 대시보드</h1>
    <div class="subtitle">뉴스 수집 → 스크립트 → 썸네일 → 영상 → YouTube 업로드</div>
  </div>
  <button class="auth-badge" id="auth-status-btn" onclick="checkAuthStatus()">
    ⏳ 인증 확인 중...
  </button>
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
    <div class="step" id="step4-indicator">
      <div class="step-num">4</div>
      <h3>영상 생성</h3>
      <p>TTS + 자막 합성</p>
    </div>
    <div class="step" id="step5-indicator">
      <div class="step-num">5</div>
      <h3>YouTube 업로드</h3>
      <p>예약 업로드 설정</p>
    </div>
  </div>

  <!-- YouTube 인증 섹션 -->
  <div class="auth-section" id="auth-section">
    <div class="section-title">
      🔐 YouTube 계정 연결
      <span class="badge" id="auth-badge-text">확인 중...</span>
    </div>
    <div id="auth-connected" style="display:none;">
      <p style="color:#4caf50; margin-bottom:10px;">✅ YouTube 계정이 연결되어 있습니다. 업로드 준비 완료!</p>
      <div class="action-row">
        <button class="btn btn-danger" onclick="revokeAuth()">🔓 연결 해제</button>
        <button class="btn btn-copy" onclick="exportToken()">📋 토큰 내보내기 (Railway용)</button>
      </div>
      <div id="token-export-section" style="display:none;" class="token-export-box">
        <h4>🚀 Railway 환경변수 설정</h4>
        <p>아래 값을 Railway 대시보드 → Variables에 추가하세요:</p>
        <p style="color:#ffcc00; margin-bottom:6px;"><strong>변수명: YOUTUBE_TOKEN_PICKLE</strong></p>
        <div class="token-value" id="token-value-display">로딩 중...</div>
        <button class="btn btn-copy" onclick="copyTokenValue()">📋 값 복사</button>
      </div>
    </div>
    <div id="auth-disconnected">
      <p style="color:#aaa; margin-bottom:12px;">YouTube 채널에 업로드하려면 계정 연결이 필요합니다.</p>
      <button class="btn btn-success" onclick="startAuth()" id="auth-start-btn">
        🔗 YouTube 계정 연결하기
      </button>
      <div id="auth-url-section" style="display:none; margin-top:15px;">
        <p style="font-size:0.85rem; color:#aaa; margin-bottom:8px;">
          아래 링크를 클릭하거나 복사해서 브라우저에서 열어주세요:
        </p>
        <div class="auth-url-box" id="auth-url-display" onclick="copyAuthUrl()">
          인증 URL 생성 중...
        </div>
        <p style="font-size:0.8rem; color:#666; margin-bottom:10px;">
          👆 클릭하면 URL이 복사되고 새 탭이 열립니다. Google 계정으로 로그인 후 허용을 눌러주세요.
        </p>
        <div class="loading" id="auth-loading" style="display:flex;">
          <span class="spinner"></span>인증 대기 중... (브라우저에서 Google 계정으로 로그인해주세요)
        </div>
      </div>
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

  <!-- STEP 5: YouTube 업로드 -->
  <div class="section" id="section-upload">
    <div class="section-title">
      <span>📤 YouTube 업로드</span>
      <span class="badge">STEP 5</span>
    </div>

    <div id="upload-no-video" style="color:#666; font-size:0.88rem; padding:10px 0;">
      ⬆️ 먼저 영상을 생성해주세요 (STEP 4)
    </div>

    <div id="upload-ready" style="display:none;">
      <div class="upload-grid">
        <!-- 한국어 채널 -->
        <div class="upload-card">
          <h3>🇰🇷 닥스삼부자 채널</h3>
          <span class="channel-badge channel-ko">@mydachshundtrio</span>
          <div class="schedule-info">
            <strong>업로드 일정:</strong> 화/목/토 오후 9시 (KST)<br>
            <strong>다음 예약:</strong> <span id="next-schedule-ko">계산 중...</span>
          </div>
          <div class="input-group" style="margin-bottom:8px;">
            <label>영상 제목</label>
            <input type="text" class="video-title-input" id="upload-title-ko" placeholder="팡사부가 알려주는 트럼프의 진짜 속셈 #Shorts">
          </div>
          <div class="input-group" style="margin-bottom:8px;">
            <label>설명</label>
            <textarea class="video-desc-input" id="upload-desc-ko" rows="3" placeholder="팡사부와 함께 알아보는 국제 정세의 이면..."></textarea>
          </div>
          <div class="upload-options">
            <label><input type="radio" name="upload-time-ko" value="schedule" checked> 자동 예약 업로드 (다음 화/목/토 21:00)</label>
            <label><input type="radio" name="upload-time-ko" value="now"> 지금 즉시 업로드 (비공개)</label>
            <label><input type="radio" name="upload-time-ko" value="custom"> 직접 시간 지정</label>
          </div>
          <input type="datetime-local" class="datetime-input" id="custom-time-ko" style="display:none;">
          <button class="btn btn-upload" onclick="uploadToYouTube('korean')" id="upload-ko-btn" disabled>
            ▶ 한국어 채널 업로드
          </button>
          <div class="loading" id="upload-ko-loading">
            <span class="spinner"></span>업로드 중... (파일 크기에 따라 1~5분 소요)
          </div>
          <div id="upload-ko-result"></div>
        </div>

        <!-- 영어 채널 -->
        <div class="upload-card">
          <h3>🌍 DrPangPsych 채널</h3>
          <span class="channel-badge channel-en">@DrPangPsych</span>
          <div class="schedule-info">
            <strong>업로드 일정:</strong> 월/수/금 오전 1시 (KST)<br>
            <strong>다음 예약:</strong> <span id="next-schedule-en">계산 중...</span>
          </div>
          <div class="input-group" style="margin-bottom:8px;">
            <label>영상 제목</label>
            <input type="text" class="video-title-input" id="upload-title-en" placeholder="What's Trump Really After? PangSabu Explains #Shorts">
          </div>
          <div class="input-group" style="margin-bottom:8px;">
            <label>설명</label>
            <textarea class="video-desc-input" id="upload-desc-en" rows="3" placeholder="PangSabu breaks down the hidden motives behind..."></textarea>
          </div>
          <div class="upload-options">
            <label><input type="radio" name="upload-time-en" value="schedule" checked> 자동 예약 업로드 (다음 월/수/금 01:00)</label>
            <label><input type="radio" name="upload-time-en" value="now"> 지금 즉시 업로드 (비공개)</label>
            <label><input type="radio" name="upload-time-en" value="custom"> 직접 시간 지정</label>
          </div>
          <input type="datetime-local" class="datetime-input" id="custom-time-en" style="display:none;">
          <button class="btn btn-upload" onclick="uploadToYouTube('english')" id="upload-en-btn" disabled>
            ▶ 영어 채널 업로드
          </button>
          <div class="loading" id="upload-en-loading">
            <span class="spinner"></span>업로드 중... (파일 크기에 따라 1~5분 소요)
          </div>
          <div id="upload-en-result"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 업로드 기록 -->
  <div class="section" id="section-history">
    <div class="section-title">
      <span>📋 최근 업로드 기록</span>
      <button class="btn btn-secondary" onclick="loadHistory()" style="font-size:0.8rem; padding:6px 14px;">새로고침</button>
    </div>
    <div id="history-list">
      <p style="color:#666; font-size:0.85rem;">YouTube 계정 연결 후 업로드 기록이 표시됩니다.</p>
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
let selectedNews = null;
let currentKeywords = [];
let currentVideoKo = null;
let currentVideoEn = null;
let currentThumbKo = null;
let currentThumbEn = null;
let isAuthenticated = false;

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3500);
}

// ── 인증 ──────────────────────────────────────────────

async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/status');
    const data = await res.json();
    isAuthenticated = data.authenticated;
    updateAuthUI(data);
    if (data.authenticated) {
      loadNextSchedules();
      loadHistory();
    }
  } catch(e) {
    console.error('인증 상태 확인 실패:', e);
  }
}

function updateAuthUI(data) {
  const btn = document.getElementById('auth-status-btn');
  const badge = document.getElementById('auth-badge-text');
  const connected = document.getElementById('auth-connected');
  const disconnected = document.getElementById('auth-disconnected');

  if (data.authenticated) {
    btn.className = 'auth-badge connected';
    btn.textContent = '✅ YouTube 연결됨';
    badge.className = 'badge green';
    badge.textContent = '연결됨';
    connected.style.display = 'block';
    disconnected.style.display = 'none';
    if (currentVideoKo) document.getElementById('upload-ko-btn').disabled = false;
    if (currentVideoEn) document.getElementById('upload-en-btn').disabled = false;
  } else {
    btn.className = 'auth-badge disconnected';
    btn.textContent = '❌ YouTube 미연결';
    badge.className = 'badge red';
    badge.textContent = '미연결';
    connected.style.display = 'none';
    disconnected.style.display = 'block';
  }
}

async function startAuth() {
  document.getElementById('auth-start-btn').disabled = true;
  document.getElementById('auth-start-btn').textContent = '⏳ 인증 URL 생성 중...';

  try {
    const res = await fetch('/api/auth/start', { method: 'POST' });
    const data = await res.json();

    if (data.auth_url) {
      document.getElementById('auth-url-section').style.display = 'block';
      document.getElementById('auth-url-display').textContent = data.auth_url;
      document.getElementById('auth-url-display').setAttribute('data-url', data.auth_url);
      showToast('🔗 인증 URL이 생성되었습니다. 클릭해서 복사하세요!');

      // 폴링으로 인증 완료 확인 (180초간)
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await fetch('/api/auth/status');
          const statusData = await statusRes.json();
          if (statusData.authenticated) {
            clearInterval(poll);
            updateAuthUI(statusData);
            document.getElementById('auth-url-section').style.display = 'none';
            document.getElementById('auth-loading').style.display = 'none';
            showToast('✅ YouTube 계정 연결 완료!');
            loadNextSchedules();
            loadHistory();
          } else if (attempts >= 60) {
            clearInterval(poll);
            document.getElementById('auth-start-btn').disabled = false;
            document.getElementById('auth-start-btn').textContent = '🔗 YouTube 계정 연결하기';
            showToast('⏰ 인증 시간 초과. 다시 시도해주세요.');
          }
        } catch(e) {}
      }, 3000);
    } else {
      document.getElementById('auth-start-btn').disabled = false;
      document.getElementById('auth-start-btn').textContent = '🔗 YouTube 계정 연결하기';
      alert('오류: ' + (data.error || '인증 URL 생성 실패'));
    }
  } catch(e) {
    document.getElementById('auth-start-btn').disabled = false;
    document.getElementById('auth-start-btn').textContent = '🔗 YouTube 계정 연결하기';
    alert('오류: ' + e.message);
  }
}

function copyAuthUrl() {
  const url = document.getElementById('auth-url-display').getAttribute('data-url')
            || document.getElementById('auth-url-display').textContent;
  if (url && url.startsWith('http')) {
    navigator.clipboard.writeText(url).then(() => {
      showToast('📋 인증 URL이 클립보드에 복사되었습니다!');
    }).catch(() => {});
    window.open(url, '_blank');
  }
}

async function revokeAuth() {
  if (!confirm('YouTube 계정 연결을 해제하시겠습니까?')) return;
  try {
    await fetch('/api/auth/revoke', { method: 'POST' });
    isAuthenticated = false;
    updateAuthUI({ authenticated: false });
    showToast('🔓 YouTube 계정 연결이 해제되었습니다.');
  } catch(e) {
    alert('오류: ' + e.message);
  }
}

async function exportToken() {
  const section = document.getElementById('token-export-section');
  if (section.style.display !== 'none') {
    section.style.display = 'none';
    return;
  }
  try {
    const res = await fetch('/api/auth/export-token');
    const data = await res.json();
    document.getElementById('token-value-display').textContent = data.token || '토큰 없음';
    section.style.display = 'block';
  } catch(e) {
    alert('오류: ' + e.message);
  }
}

function copyTokenValue() {
  const val = document.getElementById('token-value-display').textContent;
  navigator.clipboard.writeText(val).then(() => {
    showToast('📋 토큰 값이 복사되었습니다! Railway Variables에 붙여넣으세요.');
  });
}

// ── 예약 시간 ──────────────────────────────────────────

async function loadNextSchedules() {
  try {
    const res = await fetch('/api/schedule/next');
    const data = await res.json();
    if (data.korean) document.getElementById('next-schedule-ko').textContent = data.korean;
    if (data.english) document.getElementById('next-schedule-en').textContent = data.english;
  } catch(e) {}
}

// ── 뉴스 ──────────────────────────────────────────────

async function fetchNews() {
  document.getElementById('news-loading').style.display = 'flex';
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
    document.getElementById('step1-indicator').classList.add('done');
    showToast('✅ 뉴스 수집 완료!');
  } catch(e) {
    document.getElementById('news-loading').style.display = 'none';
    document.getElementById('news-list').innerHTML = `<p style="color:#f66">연결 오류: ${e.message}</p>`;
  }
}

function selectNews(idx, story) {
  document.querySelectorAll('.news-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`news-${idx}`).classList.add('selected');
  selectedNews = story;
  currentKeywords = story.keywords || [];
  document.getElementById('script-btn').disabled = false;
  document.getElementById('step2-indicator').classList.add('active');
  showToast('✅ 소재 선택됨: ' + story.title.substring(0, 30) + '...');
}

// ── 스크립트 ──────────────────────────────────────────

async function generateScript() {
  if (!selectedNews) return;
  document.getElementById('script-loading').style.display = 'flex';
  document.getElementById('script-result').style.display = 'none';
  try {
    const res = await fetch('/api/script', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ title: selectedNews.title, summary: selectedNews.summary })
    });
    const data = await res.json();
    document.getElementById('script-loading').style.display = 'none';
    if (data.error) { alert('오류: ' + data.error); return; }

    document.getElementById('script-ko').value = data.korean || data.raw || '';
    document.getElementById('script-en').value = data.english || '';
    const tagsHtml = (data.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
    document.getElementById('tags-box').innerHTML = tagsHtml;
    if (data.thumbnail_ko) document.getElementById('thumb-ko').value = data.thumbnail_ko;
    if (data.thumbnail_en) document.getElementById('thumb-en').value = data.thumbnail_en;

    const koTitle = `팡사부가 알려주는 ${data.thumbnail_ko || selectedNews.title.substring(0,15)} #Shorts`;
    const enTitle = `PangSabu: ${data.thumbnail_en || 'Hidden Truth'} #Shorts`;
    document.getElementById('upload-title-ko').value = koTitle;
    document.getElementById('upload-title-en').value = enTitle;
    const koDesc = (data.korean||'').substring(0,100) + '...\n\n팡사부와 함께 알아보는 국제 정세의 이면!\n#팡사부 #닥스삼부자 #지정학 #경제분석 #Shorts';
    const enDesc = (data.english||'').substring(0,100) + '...\n\nPangSabu breaks down the hidden motives!\n#PangSabu #DrPangPsych #geopolitics #Shorts';
    document.getElementById('upload-desc-ko').value = koDesc;
    document.getElementById('upload-desc-en').value = enDesc;

    document.getElementById('script-result').style.display = 'block';
    document.getElementById('step2-indicator').classList.add('done');
    document.getElementById('step3-indicator').classList.add('active');
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

// ── 썸네일 ──────────────────────────────────────────

async function generateThumbnail() {
  const ko = document.getElementById('thumb-ko').value.trim();
  const en = document.getElementById('thumb-en').value.trim();
  if (!ko || !en) { alert('한국어와 영어 텍스트를 모두 입력해주세요.'); return; }
  document.getElementById('thumb-loading').style.display = 'flex';
  document.getElementById('thumb-preview').style.display = 'none';
  try {
    const res = await fetch('/api/thumbnail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text_ko: ko, text_en: en, keywords: currentKeywords })
    });
    const data = await res.json();
    document.getElementById('thumb-loading').style.display = 'none';
    if (data.error) { alert('오류: ' + data.error); return; }
    currentThumbKo = data.korean_file;
    currentThumbEn = data.english_file;
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
    document.getElementById('step3-indicator').classList.add('done');
    document.getElementById('step4-indicator').classList.add('active');
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    showToast('✅ 썸네일 생성 완료!');
  } catch(e) {
    document.getElementById('thumb-loading').style.display = 'none';
    alert('오류: ' + e.message);
  }
}

// ── 영상 생성 ──────────────────────────────────────────

async function generateVideo(channel) {
  const ko = document.getElementById('script-ko').value;
  const en = document.getElementById('script-en').value;
  if (!ko && !en) { alert('먼저 스크립트를 생성해주세요.'); return; }
  document.getElementById('video-loading').style.display = 'flex';
  document.getElementById('video-result').style.display = 'none';
  document.getElementById('video-ko-btn').disabled = true;
  document.getElementById('video-en-btn').disabled = true;
  try {
    const res = await fetch('/api/video', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ script_ko: ko, script_en: en, keywords: currentKeywords, channel: channel })
    });
    const data = await res.json();
    document.getElementById('video-loading').style.display = 'none';
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    if (data.error) { alert('오류: ' + data.error); return; }

    if (channel === 'korean') currentVideoKo = data.video_file;
    else currentVideoEn = data.video_file;

    const label = channel === 'korean' ? '🇰🇷 한국어 (닥스삼부자)' : '🌍 영어 (DrPangPsych)';
    document.getElementById('video-preview').innerHTML = `
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
    document.getElementById('step4-indicator').classList.add('done');
    document.getElementById('step5-indicator').classList.add('active');
    document.getElementById('upload-no-video').style.display = 'none';
    document.getElementById('upload-ready').style.display = 'block';
    if (isAuthenticated) {
      if (channel === 'korean') document.getElementById('upload-ko-btn').disabled = false;
      if (channel === 'english') document.getElementById('upload-en-btn').disabled = false;
    }
    showToast('✅ 영상 생성 완료! ' + data.duration.toFixed(0) + '초');
  } catch(e) {
    document.getElementById('video-loading').style.display = 'none';
    document.getElementById('video-ko-btn').disabled = false;
    document.getElementById('video-en-btn').disabled = false;
    alert('오류: ' + e.message);
  }
}

// ── YouTube 업로드 ──────────────────────────────────────

async function uploadToYouTube(channel) {
  if (!isAuthenticated) { alert('YouTube 계정을 먼저 연결해주세요!'); return; }
  const videoFile = channel === 'korean' ? currentVideoKo : currentVideoEn;
  if (!videoFile) { alert('업로드할 영상이 없습니다. 먼저 영상을 생성해주세요.'); return; }

  const sfx = channel === 'korean' ? 'ko' : 'en';
  const title = document.getElementById(`upload-title-${sfx}`).value;
  const desc = document.getElementById(`upload-desc-${sfx}`).value;
  const timeOption = document.querySelector(`input[name="upload-time-${sfx}"]:checked`).value;
  const customTime = document.getElementById(`custom-time-${sfx}`).value;
  const thumbFile = channel === 'korean' ? currentThumbKo : currentThumbEn;

  if (!title) { alert('영상 제목을 입력해주세요.'); return; }

  document.getElementById(`upload-${sfx}-loading`).style.display = 'flex';
  document.getElementById(`upload-${sfx}-result`).innerHTML = '';
  document.getElementById(`upload-${sfx}-btn`).disabled = true;

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        channel, video_file: videoFile, thumbnail_file: thumbFile,
        title, description: desc, time_option: timeOption, custom_time: customTime
      })
    });
    const data = await res.json();
    document.getElementById(`upload-${sfx}-loading`).style.display = 'none';
    document.getElementById(`upload-${sfx}-btn`).disabled = false;

    if (data.error) {
      document.getElementById(`upload-${sfx}-result`).innerHTML =
        `<div class="upload-result error">❌ 업로드 실패: ${data.error}</div>`;
      return;
    }
    document.getElementById(`upload-${sfx}-result`).innerHTML = `
      <div class="upload-result">
        ✅ <strong>${data.message}</strong><br>
        영상 ID: ${data.video_id}<br>
        <a href="${data.shorts_url}" target="_blank">🔗 YouTube Shorts 링크</a>
        ${data.scheduled_at ? `<br>⏰ 예약 시간: ${data.scheduled_at}` : ''}
      </div>
    `;
    document.getElementById('step5-indicator').classList.add('done');
    showToast('✅ YouTube 업로드 완료!');
    loadHistory();
  } catch(e) {
    document.getElementById(`upload-${sfx}-loading`).style.display = 'none';
    document.getElementById(`upload-${sfx}-btn`).disabled = false;
    document.getElementById(`upload-${sfx}-result`).innerHTML =
      `<div class="upload-result error">❌ 오류: ${e.message}</div>`;
  }
}

// ── 업로드 기록 ──────────────────────────────────────────

async function loadHistory() {
  if (!isAuthenticated) return;
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    const list = document.getElementById('history-list');
    if (!data.videos || data.videos.length === 0) {
      list.innerHTML = '<p style="color:#666; font-size:0.85rem;">업로드된 영상이 없습니다.</p>';
      return;
    }
    list.innerHTML = data.videos.map(v => `
      <div class="history-item">
        <div class="title">${v.title}</div>
        <div class="date">${v.published_at ? v.published_at.substring(0,10) : ''}</div>
        <a href="${v.url}" target="_blank">▶ 보기</a>
      </div>
    `).join('');
  } catch(e) {}
}

// ── 라디오 버튼 이벤트 + 초기화 ──────────────────────────────────────────

window.onload = function() {
  checkAuthStatus();
  loadNextSchedules();

  ['ko', 'en'].forEach(sfx => {
    document.querySelectorAll(`input[name="upload-time-${sfx}"]`).forEach(r => {
      r.addEventListener('change', () => {
        document.getElementById(`custom-time-${sfx}`).style.display =
          document.querySelector(`input[name="upload-time-${sfx}"]:checked`).value === 'custom' ? 'block' : 'none';
      });
    });
  });
};
</script>
</body>
</html>
"""


# ─── Flask 라우트 ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/auth/status")
def api_auth_status():
    return jsonify(check_auth_status())


@app.route("/api/auth/start", methods=["POST"])
def api_auth_start():
    try:
        auth_url, result_container = start_oauth_local_server()
        if auth_url:
            return jsonify({'auth_url': auth_url, 'success': True})
        else:
            return jsonify({'error': '인증 URL 생성 실패. credentials.json 파일을 확인해주세요.', 'success': False})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})


@app.route("/api/auth/revoke", methods=["POST"])
def api_auth_revoke():
    return jsonify(revoke_auth())


@app.route("/api/auth/export-token")
def api_auth_export_token():
    """Railway 환경변수 설정용 토큰 내보내기"""
    token_b64 = get_token_as_base64()
    return jsonify({'token': token_b64})


@app.route("/api/schedule/next")
def api_schedule_next():
    try:
        ko_time = get_next_schedule_time('korean')
        en_time = get_next_schedule_time('english')
        return jsonify({
            'korean': ko_time.strftime('%m/%d(%a) %H:%M KST'),
            'english': en_time.strftime('%m/%d(%a) %H:%M KST'),
        })
    except Exception as e:
        return jsonify({'error': str(e)})


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
        result = generate_script(data.get("title", ""), data.get("summary", ""))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/thumbnail", methods=["POST"])
def api_thumbnail():
    try:
        data = request.get_json()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ko_file = f"thumb_korean_{timestamp}.png"
        en_file = f"thumb_english_{timestamp}.png"
        ko_path = f"/home/ubuntu/pangsabu/thumbnails/{ko_file}"
        en_path = f"/home/ubuntu/pangsabu/thumbnails/{en_file}"
        generate_thumbnail(data.get("text_ko",""), data.get("text_en",""), data.get("keywords",[]), ko_path, "korean")
        generate_thumbnail(data.get("text_ko",""), data.get("text_en",""), data.get("keywords",[]), en_path, "english")
        return jsonify({"korean_file": ko_file, "english_file": en_file})
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        channel = data.get("channel", "korean")
        video_file = f"pangsabu_{channel}_{timestamp}.mp4"
        video_path = f"/home/ubuntu/pangsabu/videos/{video_file}"
        result = generate_video(
            script_ko=data.get("script_ko",""),
            script_en=data.get("script_en",""),
            keywords=data.get("keywords",[]),
            channel=channel,
            output_path=video_path
        )
        return jsonify({"video_file": video_file, "duration": result["duration"]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route("/video/<filename>")
def serve_video(filename):
    path = f"/home/ubuntu/pangsabu/videos/{filename}"
    return send_file(path, mimetype="video/mp4")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    try:
        data = request.get_json()
        channel = data.get("channel", "korean")
        video_path = f"/home/ubuntu/pangsabu/videos/{data.get('video_file','')}"
        thumb_file = data.get("thumbnail_file","")
        thumb_path = f"/home/ubuntu/pangsabu/thumbnails/{thumb_file}" if thumb_file else None

        if not os.path.exists(video_path):
            return jsonify({"error": f"영상 파일을 찾을 수 없습니다"})

        time_option = data.get("time_option", "schedule")
        schedule_time = None
        privacy = 'private'

        if time_option == 'schedule':
            schedule_time = get_next_schedule_time(channel)
        elif time_option == 'custom' and data.get("custom_time"):
            schedule_time = datetime.fromisoformat(data["custom_time"])

        result = upload_video(
            video_path=video_path,
            title=data.get("title",""),
            description=data.get("description",""),
            schedule_time=schedule_time,
            privacy=privacy,
            thumbnail_path=thumb_path,
            channel_type=channel
        )
        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)})


@app.route("/api/history")
def api_history():
    try:
        videos = list_uploaded_videos(max_results=10)
        return jsonify({"videos": videos})
    except Exception as e:
        return jsonify({"error": str(e), "videos": []})


if __name__ == "__main__":
    for d in ["thumbnails", "audio", "videos", "frames"]:
        os.makedirs(f"/home/ubuntu/pangsabu/{d}", exist_ok=True)
    port = int(os.environ.get("PORT", 7860))
    print(f"🐾 팡사부 대시보드 시작: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
