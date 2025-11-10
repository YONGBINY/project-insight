import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json # json 라이브러리 추가

# --- 1. 설정 및 데이터 로딩 ---

# 데이터 저장 경로 설정
LOG_PATH = "data/log.csv"
CHALLENGES_PATH = "data/challenges.json"

# 로깅 함수 (이전 설계와 동일하게, 더 정교하게 구현)
def log_event(session_id, user_id, problem_id, event_type, event_target, value_1=None, value_2=None):
    """사용자의 모든 행동을 정교하게 기록하는 함수"""
    timestamp = datetime.now()
    log_entry = {
        "timestamp": [timestamp], "session_id": [session_id], "user_id": [user_id],
        "problem_id": [problem_id], "event_type": [event_type], "event_target": [event_target],
        "value_1": [value_1], "value_2": [value_2]
    }
    
    df_entry = pd.DataFrame(log_entry)

    if not os.path.exists(LOG_PATH):
        df_entry.to_csv(LOG_PATH, index=False, encoding='utf-8-sig')
    else:
        df_entry.to_csv(LOG_PATH, mode='a', header=False, index=False, encoding='utf-8-sig')

# 문제 데이터 로드 함수
@st.cache_data # Streamlit 캐시 기능으로, 파일이 바뀌지 않으면 다시 읽지 않음 (성능 향상)
def load_challenges():
    """challenges.json 파일에서 문제 데이터를 불러오는 함수"""
    with open(CHALLENGES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 2. 앱 초기화 및 상태 관리 ---

challenges = load_challenges()
total_problems = len(challenges)

if 'current_problem' not in st.session_state:
    # 세션 상태 초기화
    st.session_state.current_problem = 0
    st.session_state.session_id = f"sess_{int(datetime.now().timestamp())}"
    st.session_state.user_id = f"user_{int(datetime.now().timestamp())}" # 간단한 익명 ID
    st.session_state.answers = [None] * total_problems
    
    # 시작 이벤트 기록
    log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'start')

# --- 3. UI 렌더링 및 로직 처리 ---

st.title("🧠 인지 프로파일링 챌린지")
st.progress((st.session_state.current_problem) / total_problems) # 진행률 표시

# 챌린지 종료 화면
if st.session_state.current_problem >= total_problems:
    st.success("챌린지를 완료했습니다! 참여해주셔서 감사합니다.")
    st.balloons()
    
    # 종료 이벤트 기록
    log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'end')
    
    # (선택) 결과 요약 보여주기
    correct_answers = 0
    for i, user_ans in enumerate(st.session_state.answers):
        if str(user_ans) == str(challenges[i]['correct_answer']):
            correct_answers += 1
    st.write(f"총 {total_problems}문제 중 {correct_answers}문제를 맞혔습니다.")
    
else:
    # 현재 문제 정보 가져오기
    problem_index = st.session_state.current_problem
    problem = challenges[problem_index]
    problem_id = problem['id']

    st.header(f"Part {problem_id[0]}: {problem['part']}")
    st.subheader(f"Question {problem_index + 1}/{total_problems}")
    st.markdown(problem['question'])

    user_answer = None
    # 답변 유형에 따라 다른 입력 방식 제공
    if problem['answer_type'] == 'text_input':
        user_answer = st.text_input("정답:", key=f"answer_{problem_id}")
    elif problem['answer_type'] == 'multiple_choice':
        user_answer = st.radio("선택:", options=problem['options'], key=f"answer_{problem_id}")

    # 버튼 레이아웃
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("힌트 보기", key=f"hint_{problem_id}"):
            st.info(problem['hint'])
            log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'CLICK', 'hint_button')

    with col2:
        if st.button("다음 문제로", key=f"submit_{problem_id}"):
            # 제출 이벤트 기록
            is_correct = (str(user_answer) == str(problem['correct_answer']))
            log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'SUBMIT', 'submit_button', user_answer, is_correct)
            
            # 답변 저장 및 다음 문제로 상태 변경
            st.session_state.answers[problem_index] = user_answer
            st.session_state.current_problem += 1
            st.rerun() # 화면을 즉시 새로고침하여 다음 문제로 넘어감