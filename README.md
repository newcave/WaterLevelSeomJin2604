# 🌊 WaterLevelSim — 섬진강 수위 예측 시스템

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://YOUR_APP.streamlit.app)
[![CI](https://github.com/YOUR_ID/waterlevel-seomjin/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ID/waterlevel-seomjin/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-82%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**K-water WaterLevelSim** (C++/Windows 2021) → **Python 3 완전 이식**  
scipy 최적화 파이프라인 + Streamlit 대시보드 + 3-이벤트 검증

---

## ✨ 핵심 성과

| 구분 | RMSE | 비고 |
|------|------|------|
| 베이스라인 | 2.785 m | DLL 없음, Python만 |
| per_station 최적화 | **0.743 m** | 73% 개선, ~8초 |
| timeseries 최적화 | **0.675 m** | 76% 개선, ~18초 |
| 원본 EXE 3-이벤트 평균 | 2.209 m | ← **Python 2.5× 우수** |

> **Event3 극한 홍수**: Python(1.057m) vs 원본 EXE(5.579m) — **Python 역전!**

---

## 🚀 빠른 시작

```bash
git clone https://github.com/YOUR_ID/waterlevel-seomjin
cd waterlevel-seomjin
pip install -r requirements.txt
streamlit run app.py
```

또는 Streamlit Cloud 바로가기: [![Open App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://YOUR_APP.streamlit.app)

---

## 📱 앱 페이지

| 페이지 | 기능 |
|--------|------|
| 🏠 홈 | 프로젝트 개요, RMSE 요약, 빠른 시작 |
| 🔵 시뮬레이션 | NC/NPZ 로드 → 베이스라인 예측 → Plotly 시계열·산점도 |
| 🟣 최적화 | FlowOptimizer (global/per_station/timeseries) 실시간 실행 |
| 🟢 검증 | 3-이벤트 교차 검증 + CSV 다운로드 |
| 🔬 파라미터탐색기 | c_sm 히트맵, Q 계수, Event Criteria, 단일 스텝 계산기 |

---

## 📁 구조

```
waterlevel-seomjin/
├── app.py                      홈 페이지 (Streamlit 진입점)
├── pages/
│   ├── 1_🔵_시뮬레이션.py
│   ├── 2_🟣_최적화.py
│   ├── 3_🟢_검증.py
│   └── 4_🔬_파라미터탐색기.py
├── waterlevel_sim/             Python 패키지 (8 모듈)
│   ├── nc_reader.py            K-Water HEC-RAS NetCDF 파서
│   ├── data_library.py         DataLibrary.cpp 이식
│   ├── simulator.py            ML 예측 엔진
│   ├── routing.py              FlowRouter (HEinsSim 근사)
│   ├── optimizer.py            FlowOptimizer (EinsOpt 대체)
│   ├── metrics.py              RMSE/MAE/NSE
│   └── npz_loader.py           경량 NPZ 로더
├── tests/                      pytest (82 테스트, 전원 통과)
├── .github/workflows/ci.yml   GitHub Actions (Python 3.9~3.11)
├── data/
│   ├── ParamSetforcxx.csv      ML 파라미터 (8.9 KB)
│   ├── tesr_demo.npz           Event1 (45 KB)
│   ├── tesr2_demo.npz          Event2 (43 KB)
│   └── tesr3_demo.npz          Event3 (46 KB)
├── .streamlit/config.toml
├── requirements.txt
└── DEPLOY.md                   배포 가이드
```

---

## 📐 예측 모델

```
WL(station, t+1) = c_sm + a_sm × Q(station, t) + b_sm × Q(station, t-1)
```

| 파라미터 | 의미 | 값 범위 |
|----------|------|---------|
| `c_sm` | 기저 수위 [m] | 0.1 ~ 130m |
| `a_sm` | Q 현재 계수 | 0.001 ~ 0.005 |
| `b_sm` | Q 이전 계수 | −0.007 ~ 0.005 |
| `sm` | 유량 체계 (0~3) | event_criteria 기반 자동 선택 |

---

## 🔧 API

```python
from waterlevel_sim import DataLibrary, WaterLevelSimulator, FlowOptimizer
from waterlevel_sim.npz_loader import load_demo

nc  = load_demo("tesr")                        # NC 없이 45KB 데모 로드
dl  = DataLibrary("data/ParamSetforcxx.csv")
res = WaterLevelSimulator(dl, nc.wl, nc.q_station).run()
print(f"RMSE: {res.rmse_mean:.3f} m")

opt    = FlowOptimizer(dl, nc.wl, nc.q_station)
result = opt.optimize("per_station")           # 73% 개선
print(result.summary())
```

---

## 🧪 테스트

```bash
pytest tests/ -v          # 82개 테스트
pytest tests/ -q --tb=no  # 요약만
```

---

## 📝 라이선스

MIT License

## 🙏 참고
- Claude Sonnet (Anthropic)
