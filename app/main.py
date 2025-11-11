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
    
    # [추가] 시작 시간과 힌트 카운트 초기화
    st.session_state.start_time = datetime.now()
    st.session_state.hint_clicks = 0
    
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
        
        # [추가] 힌트 클릭 카운트 증가
        st.session_state.hint_clicks += 1

        log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'CLICK', 'hint_button')

# --- 3.3. 챌린지 완료 화면 ---
else:
    st.success("챌린지를 완료했습니다! 당신의 문제 해결 스타일을 분석해봤어요.")
    st.balloons()
    
    if 'session_ended' not in st.session_state:
        # 종료 시간 기록 및 총 소요 시간 계산
        end_time = datetime.now()
        total_duration_seconds = (end_time - st.session_state.start_time).total_seconds()
        st.session_state.total_duration = total_duration_seconds # 나중에 사용할 수 있도록 저장

        log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'end', value_1=total_duration_seconds)
        st.session_state.session_ended = True

    # --- 실시간 규칙 기반 페르소나 분석 ---

    # 1. 최종 성적 및 행동 데이터 계산
    correct_answers = sum(1 for i, ans in enumerate(st.session_state.answers) if str(ans) == str(challenges[i]['correct_answer']))
    correct_rate = correct_answers / total_problems
    total_time = st.session_state.get('total_duration', 300) # 혹시 모를 오류 방지 기본값
    hint_count = st.session_state.get('hint_clicks', 0)

    # 2. 페르소나 판별 로직
    persona_type = "균형잡힌 해결사" # 기본값

    TIME_THRESHOLD_FAST = 180  # 3분
    TIME_THRESHOLD_SLOW = 420  # 7분
    ACCURACY_THRESHOLD_HIGH = 0.77 # 7/9 (약 77%)
    ACCURACY_THRESHOLD_LOW = 0.44  # 4/9 (약 44%)

    if total_time < TIME_THRESHOLD_FAST and correct_rate >= ACCURACY_THRESHOLD_HIGH:
        persona_type = "신속한 전략가"
    elif total_time > TIME_THRESHOLD_SLOW and correct_rate >= ACCURACY_THRESHOLD_HIGH:
        persona_type = "신중한 탐험가"
    elif total_time < TIME_THRESHOLD_FAST and correct_rate < ACCURACY_THRESHOLD_HIGH:
        persona_type = "직관적인 해결사"
    elif correct_rate <= ACCURACY_THRESHOLD_LOW or (total_time > TIME_THRESHOLD_SLOW and correct_rate < ACCURACY_THRESHOLD_HIGH):
        persona_type = "성실한 등반가"

    # 3. 각 페르소나에 대한 설명 딕셔너리
    persona_descriptions = {
        "신속한 전략가": {
            "icon": "⚡️", "desc": "문제의 핵심을 빠르게 파악하고, 효율적으로 정답을 찾아내는 데 능숙합니다. 마치 날카로운 검사처럼, 복잡한 문제도 군더더기 없이 해결하는 스타일입니다.", "action": "가끔은 너무 빠른 속도 때문에 놓치는 '함정'이 있을 수 있습니다. 중요한 문제 앞에서는 한 번만 더 검토하는 습관을 들인다면 완벽에 가까워질 것입니다."
        },
        "신중한 탐험가": {
            "icon": "🗺️", "desc": "돌다리도 두들겨 보고 건너는 신중한 스타일의 문제 해결사입니다. 시간을 들여 모든 가능성을 탐색하고, 가장 확실한 길을 찾아냅니다. 당신의 꼼꼼함은 실수를 용납하지 않는 가장 큰 무기입니다.", "action": "가끔은 당신의 직관을 믿고 조금 더 과감하게 나아가도 좋습니다. 모든 것이 완벽하게 준비되기를 기다리기보다, 때로는 빠른 시도가 더 나은 결과를 가져올 수도 있습니다."
        },
        "직관적인 해결사": {
            "icon": "💡", "desc": "정석적인 방법보다는 번뜩이는 직관과 창의력으로 문제에 접근하는 유형입니다. 복잡한 분석보다는 핵심을 꿰뚫는 한 방을 선호하며, 과감하게 도전하는 것을 즐깁니다.", "action": "당신의 직관은 훌륭한 자산입니다. 여기에 약간의 '논리적 검증' 과정을 더한다면, 당신의 아이디어는 더욱 빛을 발할 것입니다. 제출하기 전 '왜 이것이 답일까?'라고 스스로에게 질문하는 습관을 가져보세요."
        },
        "성실한 등반가": {
            "icon": "🧗", "desc": "어려운 문제 앞에서도 쉽게 포기하지 않는 끈기와 성실함을 가진 유형입니다. 과정 자체에 의미를 두는 당신의 꾸준함은 큰 잠재력을 의미합니다.", "action": "문제의 핵심 원리를 파악하는 연습을 꾸준히 한다면, 당신의 노력은 곧 뛰어난 결과로 이어질 것입니다."
        },
        "균형잡힌 해결사": {
            "icon": "⚖️", "desc": "속도와 정확성의 균형을 잘 맞추는 안정적인 문제 해결사입니다. 상황에 따라 신중하게 접근하기도 하고, 때로는 빠르게 판단을 내리기도 하는 유연한 사고방식을 가졌습니다.", "action": "당신의 가장 큰 장점은 '균형'입니다. 다양한 문제 해결 전략을 꾸준히 접하며, 상황에 맞는 최적의 무기를 꺼내 드는 연습을 해보세요."
        }
    }
    
    # 4. 결과 카드 UI 렌더링
    st.divider()
    
    details = persona_descriptions.get(persona_type)
    if details:
        st.markdown(f"### {details['icon']} 당신의 문제 해결 스타일은: **{persona_type}**")
        st.markdown(f"> _{details['desc']}_")
        
        # 분석 근거 동적 생성
        evidence_text = (f"당신은 **약 {total_time:.0f}초** 동안 **총 {total_problems}문제** 중 **{correct_answers}문제**를 맞혔고, "
                         f"**{hint_count}번**의 힌트를 사용했습니다. 이 패턴을 바탕으로 당신의 스타일을 분석했습니다.")
        st.info(f"**📊 분석 근거:**\n{evidence_text}")
        st.warning(f"**💡 성장 팁:**\n{details['action']}")

    # 5. [추가된 안내 문구] 데이터 기반 모델 고도화에 대한 설명 및 참여 독려
    st.divider()
    with st.expander("👀 이 분석 결과는 어떻게 만들어졌나요?"):
        st.markdown("""
        현재 보시는 분석 결과는 초기 데이터를 바탕으로 저희가 설정한 **'규칙 기반 가이드라인'**에 따라 제공됩니다. 
        이는 당신의 문제 해결 스타일을 이해하는 첫걸음입니다.

        앞으로 더 많은 분들이 챌린지에 참여해주시면, **축적된 데이터는 머신러닝 모델을 통해 더욱 정교하고 다채로운 유형으로 진화**하게 됩니다. 
        당신의 참여 하나하나가 세상을 더 잘 이해하는 지도를 만드는 데 소중한 발걸음이 됩니다.

        **주변에 이 챌린지를 공유하여 더 똑똑한 분석 모델을 함께 만들어주세요!**
        """)