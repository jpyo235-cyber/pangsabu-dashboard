"""
YouTube 업로드 모듈 - 팡사부 자동화 파이프라인
OAuth 2.0 인증 + 예약 업로드 + 썸네일 설정 지원
Railway 영구 서버 환경 대응 (환경변수로 credentials 처리)
"""
import os
import json
import pickle
import base64
import threading
from datetime import datetime, timezone, timedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.pickle')

KST = timezone(timedelta(hours=9))

# 전역 OAuth 상태
_oauth_state = {
    'pending': False,
    'auth_url': None,
    'flow': None,
    'result': None,
}


def _ensure_credentials_file():
    """
    환경변수 GOOGLE_CREDENTIALS_JSON 이 있으면 credentials.json 파일 생성
    Railway 배포 환경에서 사용
    """
    env_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if env_creds and not os.path.exists(CREDENTIALS_FILE):
        try:
            # Base64 인코딩된 경우 디코딩
            try:
                decoded = base64.b64decode(env_creds).decode('utf-8')
                creds_data = json.loads(decoded)
            except Exception:
                creds_data = json.loads(env_creds)
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(creds_data, f)
            print("환경변수에서 credentials.json 생성 완료")
        except Exception as e:
            print(f"credentials.json 생성 실패: {e}")

    # token.pickle도 환경변수에서 복원
    env_token = os.environ.get('YOUTUBE_TOKEN_PICKLE')
    if env_token and not os.path.exists(TOKEN_FILE):
        try:
            token_data = base64.b64decode(env_token)
            with open(TOKEN_FILE, 'wb') as f:
                f.write(token_data)
            print("환경변수에서 token.pickle 복원 완료")
        except Exception as e:
            print(f"token.pickle 복원 실패: {e}")


def get_token_as_base64() -> str:
    """token.pickle을 Base64로 인코딩하여 반환 (환경변수 설정용)"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return ""


def get_credentials_as_base64() -> str:
    """credentials.json을 Base64로 인코딩하여 반환 (환경변수 설정용)"""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return ""


def get_authenticated_service():
    """YouTube API 인증 서비스 반환 (토큰 파일 기반)"""
    _ensure_credentials_file()

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"토큰 갱신 실패: {e}")
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                return None
        else:
            return None  # 인증 필요

    return build('youtube', 'v3', credentials=creds)


def start_oauth_local_server():
    """
    로컬 서버를 백그라운드에서 띄워 OAuth 인증 처리
    반환: (auth_url, result_container)
    """
    _ensure_credentials_file()

    if not os.path.exists(CREDENTIALS_FILE):
        print("credentials.json 파일이 없습니다!")
        return None, None

    result_container = {'done': False, 'success': False, 'error': None}

    def _run():
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(
                port=8080,
                open_browser=False,
                success_message='인증 완료! 이 창을 닫고 대시보드로 돌아가세요.'
            )
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            result_container['done'] = True
            result_container['success'] = True
            _oauth_state['pending'] = False
            _oauth_state['result'] = 'success'
            print("OAuth 인증 완료!")
        except Exception as e:
            result_container['done'] = True
            result_container['success'] = False
            result_container['error'] = str(e)
            _oauth_state['pending'] = False
            _oauth_state['result'] = f'error: {e}'
            print(f"OAuth 인증 실패: {e}")

    # 인증 URL 미리 생성
    try:
        flow_preview = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        auth_url, _ = flow_preview.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        _oauth_state['auth_url'] = auth_url
        _oauth_state['pending'] = True
        _oauth_state['result'] = None
    except Exception as e:
        print(f'OAuth URL 생성 오류: {e}')
        return None, None

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return _oauth_state['auth_url'], result_container


def check_auth_status():
    """인증 상태 확인"""
    _ensure_credentials_file()

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
            if creds and creds.valid:
                return {'authenticated': True, 'message': 'YouTube 계정 연결됨 ✅'}
            elif creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                    return {'authenticated': True, 'message': 'YouTube 계정 연결됨 (토큰 갱신) ✅'}
                except Exception as e:
                    return {'authenticated': False, 'message': f'토큰 갱신 실패: {e}'}
        except Exception:
            pass
    return {'authenticated': False, 'message': 'YouTube 계정 연결 필요 ❌'}


def revoke_auth():
    """인증 토큰 삭제"""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    return {'success': True, 'message': '인증 해제 완료'}


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list = None,
    schedule_time=None,
    privacy: str = 'private',
    thumbnail_path: str = None,
    channel_type: str = 'korean'
):
    """
    YouTube에 영상 업로드

    Args:
        video_path: 업로드할 영상 파일 경로
        title: 영상 제목
        description: 영상 설명
        tags: 태그 리스트
        schedule_time: 예약 업로드 시간 (datetime 또는 ISO 문자열, None이면 즉시)
        privacy: 공개 설정 ('public', 'private', 'unlisted')
        thumbnail_path: 썸네일 이미지 경로 (선택)
        channel_type: 'korean' 또는 'english'

    Returns:
        dict: {'success': bool, 'video_id': str, 'url': str, 'error': str}
    """
    youtube = get_authenticated_service()
    if not youtube:
        return {
            'success': False,
            'error': 'YouTube 인증이 필요합니다. 먼저 계정을 연결해주세요.'
        }

    try:
        # 예약 시간 처리
        publish_at = None
        actual_privacy = privacy

        if schedule_time:
            if isinstance(schedule_time, str):
                schedule_time = datetime.fromisoformat(schedule_time)
            if schedule_time.tzinfo is None:
                schedule_time = schedule_time.replace(tzinfo=KST)
            publish_at = schedule_time.isoformat()
            actual_privacy = 'private'  # 예약 업로드는 반드시 private

        # 채널별 기본 태그
        default_tags_ko = ['팡사부', '닥스삼부자', '지정학', '경제분석', '국제정세', 'Shorts', '쇼츠']
        default_tags_en = ['PangSabu', 'DrPangPsych', 'geopolitics', 'economics', 'analysis', 'Shorts']
        base_tags = default_tags_ko if channel_type == 'korean' else default_tags_en
        all_tags = list(set(base_tags + (tags or [])))[:15]

        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000],
                'tags': all_tags,
                'categoryId': '25',  # News & Politics
                'defaultLanguage': 'ko' if channel_type == 'korean' else 'en',
            },
            'status': {
                'privacyStatus': actual_privacy,
                'selfDeclaredMadeForKids': False,
                'madeForKids': False,
            }
        }

        if publish_at:
            body['status']['publishAt'] = publish_at

        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024 * 1024 * 5  # 5MB 청크
        )

        request_obj = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status_obj, response = request_obj.next_chunk()
            if status_obj:
                progress = int(status_obj.progress() * 100)
                print(f"업로드 진행: {progress}%")

        video_id = response['id']
        print(f"업로드 완료! 영상 ID: {video_id}")

        # 썸네일 설정
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/png')
                ).execute()
                print(f"썸네일 설정 완료!")
            except Exception as te:
                print(f"썸네일 설정 실패 (업로드는 성공): {te}")

        result = {
            'success': True,
            'video_id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'shorts_url': f'https://www.youtube.com/shorts/{video_id}',
        }

        if publish_at:
            result['scheduled_at'] = publish_at
            result['message'] = f'예약 업로드 설정 완료 ({schedule_time.strftime("%Y-%m-%d %H:%M KST")})'
        else:
            result['message'] = '즉시 업로드 완료'

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def get_next_schedule_time(channel_type: str) -> datetime:
    """
    채널 타입에 따른 다음 예약 업로드 시간 계산
    - 한국어 (korean): 화(1)/목(3)/토(5) 21:00 KST
    - 영어 (english): 월(0)/수(2)/금(4) 01:00 KST
    """
    now = datetime.now(KST)

    if channel_type == 'korean':
        target_days = [1, 3, 5]
        target_hour = 21
        target_minute = 0
    else:
        target_days = [0, 2, 4]
        target_hour = 1
        target_minute = 0

    for days_ahead in range(8):
        candidate = now + timedelta(days=days_ahead)
        candidate = candidate.replace(
            hour=target_hour,
            minute=target_minute,
            second=0,
            microsecond=0
        )
        if candidate.weekday() in target_days and candidate > now:
            return candidate

    return now + timedelta(hours=1)


def list_uploaded_videos(max_results: int = 10) -> list:
    """최근 업로드된 영상 목록 조회"""
    youtube = get_authenticated_service()
    if not youtube:
        return []

    try:
        channels_response = youtube.channels().list(
            part='contentDetails,snippet',
            mine=True
        ).execute()

        if not channels_response.get('items'):
            return []

        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=max_results
        ).execute()

        videos = []
        for item in playlist_response.get('items', []):
            snippet = item['snippet']
            video_id = snippet['resourceId']['videoId']
            videos.append({
                'video_id': video_id,
                'title': snippet['title'],
                'published_at': snippet['publishedAt'],
                'url': f'https://www.youtube.com/watch?v={video_id}',
                'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
            })

        return videos

    except Exception as e:
        print(f"영상 목록 조회 오류: {e}")
        return []


if __name__ == '__main__':
    print("=== YouTube 인증 상태 확인 ===")
    status = check_auth_status()
    print(status)

    if not status['authenticated']:
        print("\nOAuth 인증을 시작합니다...")
        auth_url, result_container = start_oauth_local_server()
        if auth_url:
            print(f"\n아래 URL을 브라우저에서 열어 인증을 완료하세요:\n{auth_url}\n")
            print("인증 완료 후 Enter를 누르세요...")
            input()
            print(f"결과: {result_container}")
    else:
        # token.pickle Base64 출력 (Railway 환경변수 설정용)
        token_b64 = get_token_as_base64()
        if token_b64:
            print(f"\n[Railway 환경변수 설정용 YOUTUBE_TOKEN_PICKLE]")
            print(token_b64[:50] + "...")
