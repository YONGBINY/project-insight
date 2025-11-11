import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import gspread

# --- 1. 초기 설정 및 함수 정의 ---

CHALLENGES_PATH = "data/challenges.json"

def log_event(session_id, user_id, problem_id, event_type, event_target, value_1=None, value_2=None):
    """사용자의 행동 로그를 Google Sheet에 기록합니다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": [timestamp], "session_id": [session_id], "user_id": [user_id],
        "problem_id": [problem_id], "event_type": [event_type], "event_target": [event_target],
        "value_1": [str(value_1)], "value_2": [str(value_2)]
    }
    df_entry = pd.DataFrame(log_entry)

    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        spreadsheet = gc.open("log")
        # [주의] "시트1"은 당신의 Google Sheet 탭 이름과 정확히 일치해야 합니다.
        worksheet = spreadsheet.worksheet("시트1") 
        worksheet.append_rows(df_entry.values.tolist())
    except Exception:
        # 클라우드 인증 실패 시 로컬에 기록 (개발/테스트용 Fallback)
        log_path_local = "data/log.csv"
        if not os.path.exists(log_path_local):
            df_entry.to_csv(log_path_local, index=False, encoding='utf-8-sig')
        else:
            df_entry.to_csv(log_path_local, mode='a', header=False, index=False, encoding='utf-8-sig')

@st.cache_data
def load_challenges():
    """JSON 파일에서 문제 데이터를 불러옵니다. (캐시 사용으로 성능 최적화)"""
    with open(CHALLENGES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 2. 앱 상태 초기화 ---

challenges = load_challenges()
total_problems = len(challenges)

if 'current_problem' not in st.session_state:
    st.session_state.current_problem = 0
    st.session_state.session_id = f"sess_{int(datetime.now().timestamp())}"
    st.session_state.user_id = f"user_{int(datetime.now().timestamp())}"
    st.session_state.answers = [None] * total_problems
    log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'start')

# --- 3. 애플리케이션 UI 렌더링 ---

st.title("🧠 인지 프로파일링 챌린지")

# 3.1. 사용자 정보 수집 화면 (디자인 수정됨)
if 'demographics_submitted' not in st.session_state:
    st.info("챌린지에 참여해주셔서 감사합니다! 💡")
    
    with st.form(key='demographics_form'):
        
        # --- 1. 기프티콘 이벤트 섹션 ---
        st.subheader("🎁 챌린지 완료 감사 기프티콘!")
        st.markdown("참여해주신 분들 중 추첨을 통해 기프티콘을 드립니다. 원하시는 경우 이메일을 남겨주세요! (선택사항이며, 이벤트 목적 외에는 절대 사용되지 않습니다.)")
        email = st.text_input("이메일 (기프티콘 추첨용)", placeholder="example@gmail.com")
        
        st.divider()

        # --- 2. 연구용 정보 섹션 ---
        st.markdown("**더 나은 연구를 위해, 괜찮으시다면 아래 정보도 제공해주세요. (선택사항)**")
        age = st.selectbox("연령대를 선택해주세요.", ["선택 안 함", "10대", "20대", "30대", "40대 이상"])
        gender = st.selectbox("성별을 선택해주세요.", ["선택 안 함", "남성", "여성", "기타"])
        education = st.selectbox("최종 학력을 선택해주세요.", ["선택 안 함", "중/고등학생", "대학생", "대학원생", "기타"])
        
        # --- 3. 제출 버튼 ---
        if st.form_submit_button("챌린지 시작하기"):
            
            user_info = {
                "email": email if email else "선택 안 함", #
                "age": age, 
                "gender": gender, 
                "education": education
            }
            
            # 로그 이벤트에 user_info 전체 기록
            log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 
                      'SURVEY', 'submit_demographics', value_1=user_info)
            
            st.session_state.demographics_submitted = True
            st.rerun()

# 3.2. 챌린지 진행 화면
elif st.session_state.current_problem < total_problems:
    st.progress(st.session_state.current_problem / total_problems)
    
    problem_index = st.session_state.current_problem
    problem = challenges[problem_index]
    problem_id = problem['id']

    st.header(f"Part {problem_id[0]}: {problem['part']}")
    st.subheader(f"Question {problem_index + 1}/{total_problems}")
    st.markdown(problem['question'])

    answer_type = problem.get('answer_type', 'text_input')
    user_answer = None
    if answer_type == 'text_input':
        user_answer = st.text_input("정답:", key=f"answer_{problem_id}")
    elif answer_type == 'multiple_choice':
        user_answer = st.radio("선택:", options=problem['options'], key=f"answer_{problem_id}", index=None)

    col1, col2 = st.columns([1, 1])
    if col1.button("힌트 보기", key=f"hint_{problem_id}"):
        st.info(problem['hint'])
        log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'CLICK', 'hint_button')
    if col2.button("다음 문제로", key=f"submit_{problem_id}"):
        is_correct = (str(user_answer) == str(problem['correct_answer']))
        log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'SUBMIT', 'submit_button', user_answer, is_correct)
        st.session_state.answers[problem_index] = user_answer
        st.session_state.current_problem += 1
        st.rerun()

# 3.3. 챌린지 완료 화면
else:
    st.success("챌린지를 완료했습니다! 참여해주셔서 감사합니다.")
    st.balloons()
    
    if 'session_ended' not in st.session_state:
        log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'end')
        st.session_state.session_ended = True
    
    correct_answers = sum(1 for i, ans in enumerate(st.session_state.answers) if str(ans) == str(challenges[i]['correct_answer']))
    st.write(f"총 {total_problems}문제 중 {correct_answers}문제를 맞혔습니다.")