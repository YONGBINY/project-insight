import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import gspread
from gspread_dataframe import set_with_dataframe

# --- 1. 설정 및 핵심 함수 정의 ---

LOG_PATH = "data/log.csv"
CHALLENGES_PATH = "data/challenges.json"

def log_event(session_id, user_id, problem_id, event_type, event_target, value_1=None, value_2=None):
    """사용자의 모든 행동을 Google Sheet에 기록하는 함수"""
    timestamp = datetime.now()
    log_entry = {
        "timestamp": [timestamp], "session_id": [session_id], "user_id": [user_id],
        "problem_id": [problem_id], "event_type": [event_type], "event_target": [event_target],
        "value_1": [str(value_1)], "value_2": [str(value_2)] # 모든 값을 문자열로 변환
    }
    df_entry = pd.DataFrame(log_entry)

    try:
        # Streamlit의 Secret 기능으로 인증 정보 가져오기
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        # 'log_sheet'는 당신이 만든 Google Sheet의 이름입니다.
        spreadsheet = gc.open("log") 
        worksheet = spreadsheet.sheet1
        
        # DataFrame을 시트의 마지막 빈 행에 추가 (헤더 제외)
        worksheet.append_rows(df_entry.values.tolist())

    except Exception as e:
        # 클라우드가 아닌 로컬 환경이거나, 인증 실패 시 로컬 CSV에 대신 저장 (Fallback)
        # st.error(f"Google Sheets에 연결할 수 없습니다: {e}") # 디버깅용
        
        log_path_local = "data/log.csv"
        if not os.path.exists(log_path_local):
            df_entry.to_csv(log_path_local, index=False, encoding='utf-8-sig')
        else:
            df_entry.to_csv(log_path_local, mode='a', header=False, index=False, encoding='utf-8-sig')

@st.cache_data
def load_challenges():
    """challenges.json 파일에서 문제 데이터를 불러오는 함수"""
    with open(CHALLENGES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 2. 앱 초기화 및 상태 관리 ---

challenges = load_challenges()
total_problems = len(challenges)

if 'current_problem' not in st.session_state:
    st.session_state.current_problem = 0
    st.session_state.session_id = f"sess_{int(datetime.now().timestamp())}"
    st.session_state.user_id = f"user_{int(datetime.now().timestamp())}"
    st.session_state.answers = [None] * total_problems
    log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'start')

# --- 3. 메인 애플리케이션 렌더링 ---

st.title("🧠 인지 프로파일링 챌린지")

# --- 3.1. 사용자 정보 수집 화면 ---
if 'demographics_submitted' not in st.session_state:
    st.info("더 나은 연구를 위해, 괜찮으시다면 아래 정보 제공에 협조해주시면 감사하겠습니다. (선택사항)")
    
    with st.form(key='demographics_form'):
        age = st.selectbox("연령대를 선택해주세요.", ["선택 안 함", "10대", "20대", "30대", "40대 이상"])
        gender = st.selectbox("성별을 선택해주세요.", ["선택 안 함", "남성", "여성", "기타"])
        education = st.selectbox("최종 학력을 선택해주세요.", ["선택 안 함", "중/고등학생", "대학생", "대학원생", "기타"])
        
        submitted = st.form_submit_button("챌린지 시작하기")

        if submitted:
            user_info = {"age": age, "gender": gender, "education": education}
            log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 
                      'SURVEY', 'submit_demographics', value_1=user_info)
            
            st.session_state.demographics_submitted = True
            st.rerun()

# --- 3.2. 챌린지 진행 화면 ---
elif st.session_state.current_problem < total_problems:
    st.progress((st.session_state.current_problem) / total_problems)
    
    problem_index = st.session_state.current_problem
    problem = challenges[problem_index]
    problem_id = problem['id']

    st.header(f"Part {problem_id[0]}: {problem['part']}")
    st.subheader(f"Question {problem_index + 1}/{total_problems}")
    st.markdown(problem['question'])

    user_answer = None
    if problem['answer_type'] == 'text_input':
        user_answer = st.text_input("정답:", key=f"answer_{problem_id}")
    elif problem['answer_type'] == 'multiple_choice':
        user_answer = st.radio("선택:", options=problem['options'], key=f"answer_{problem_id}", index=None)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("힌트 보기", key=f"hint_{problem_id}"):
            st.info(problem['hint'])
            log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'CLICK', 'hint_button')
    with col2:
        if st.button("다음 문제로", key=f"submit_{problem_id}"):
            is_correct = (str(user_answer) == str(problem['correct_answer']))
            log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'SUBMIT', 'submit_button', user_answer, is_correct)
            
            st.session_state.answers[problem_index] = user_answer
            st.session_state.current_problem += 1
            st.rerun()

# --- 3.3. 챌린지 완료 화면 ---
else:
    st.success("챌린지를 완료했습니다! 참여해주셔서 감사합니다.")
    st.balloons()
    
    if 'session_ended' not in st.session_state:
        log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'end')
        st.session_state.session_ended = True
    
    correct_answers = 0
    for i, user_ans in enumerate(st.session_state.answers):
        if str(user_ans) == str(challenges[i]['correct_answer']):
            correct_answers += 1
    st.write(f"총 {total_problems}문제 중 {correct_answers}문제를 맞혔습니다.")