# GitHub + Streamlit Cloud 배포 가이드

## 1단계: GitHub 저장소 생성

```bash
# 저장소 초기화
cd waterlevel-seomjin
git init
git add .
git commit -m "Initial commit: WaterLevelSim Python 포트 v2"

# GitHub에 Push (GitHub CLI 사용)
gh repo create waterlevel-seomjin --public --source=. --push

# 또는 GitHub 웹에서 생성 후:
git remote add origin https://github.com/YOUR_USERNAME/waterlevel-seomjin.git
git branch -M main
git push -u origin main
```

## 2단계: Streamlit Cloud 배포

1. **https://share.streamlit.io** 접속
2. **New app** 클릭
3. 설정:
   - Repository: `YOUR_USERNAME/waterlevel-seomjin`
   - Branch: `main`
   - Main file path: `app.py`
4. **Deploy!** 클릭 → 자동 빌드 (~2분)

## 3단계: README 배지 업데이트

배포 완료 후 앱 URL을 README.md에 입력:
```markdown
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://YOUR_APP.streamlit.app)
```

## 파일 크기 체크 (GitHub 100MB 제한)

| 파일 | 크기 | GitHub 가능 |
|------|------|-------------|
| ParamSetforcxx.csv | 8.9 KB | ✅ |
| tesr_demo.npz | 45 KB | ✅ |
| tesr2_demo.npz | 43 KB | ✅ |
| tesr3_demo.npz | 46 KB | ✅ |
| tesr.nc | 20 MB | ❌ (.gitignore) |

NC 파일은 .gitignore에 포함. 앱에서 업로드 기능으로 사용.

## Streamlit Cloud 환경 변수 (선택)

Streamlit Cloud > App settings > Secrets:
```toml
# .streamlit/secrets.toml (로컬만, 절대 커밋 금지)
NC_DATA_PATH = "/path/to/data"
```
