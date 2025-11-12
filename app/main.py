import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
import gspread
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

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
        if "gcp_service_account" in st.secrets:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            spreadsheet = gc.open("log")
            worksheet = spreadsheet.worksheet("시트1")
            worksheet.append_rows(df_entry.values.tolist())
    except Exception as e:
        print(f"Log Error: {e}")
        # 로컬 백업
        log_path_local = "data/log.csv"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(log_path_local):
            df_entry.to_csv(log_path_local, index=False, encoding='utf-8-sig')
        else:
            df_entry.to_csv(log_path_local, mode='a', header=False, index=False, encoding='utf-8-sig')


@st.cache_data
def load_challenges():
    with open(CHALLENGES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_result_image(persona_details, stats):
    template_path = "data/template.png"
    font_path = "data/DungGeunMo.ttf"

    # 이미지 없으면 생성 (에러 방지용)
    if not os.path.exists(template_path):
        img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    else:
        img = Image.open(template_path)

    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype(font_path, size=80)
        desc_font = ImageFont.truetype(font_path, size=40)
        stats_font = ImageFont.truetype(font_path, size=50)
    except IOError:
        title_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        stats_font = ImageFont.load_default()

    img_width, img_height = img.size

    draw.text((img_width / 2, 200), f"{persona_details['icon']} {persona_details['name']}", font=title_font,
              fill="black", anchor="ms")

    desc_lines = textwrap.wrap(persona_details['desc'], width=25)
    y_text = 350
    for line in desc_lines:
        draw.text((img_width / 2, y_text), line, font=desc_font, fill="#333333", anchor="ms")
        # getbbox를 사용한 높이 계산 (pillow 10 대응)
        bbox = desc_font.getbbox(line)
        y_text += (bbox[3] - bbox[1]) + 10

    draw.text((img_width / 2, 600), f"정답률: {stats['correct_rate']:.0%}", font=stats_font, fill="blue", anchor="ms")
    draw.text((img_width / 2, 700), f"소요 시간: {stats['total_time']:.0f}초", font=stats_font, fill="green", anchor="ms")
    draw.text((img_width / 2, 800), f"힌트 사용: {stats['hint_count']}회", font=stats_font, fill="orange", anchor="ms")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def handle_hint(problem_id):
    """힌트 버튼 클릭 시 실행되는 콜백"""
    st.session_state.hint_clicks += 1
    st.session_state.show_hint_current = True  # 현재 문제에 대해 힌트를 보여줌
    log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'CLICK', 'hint_button')


def handle_submit(problem_id, correct_answer):
    """다음 문제 버튼 클릭 시 실행되는 콜백"""
    # 1. 현재 입력된 값 가져오기
    input_key = f"answer_{problem_id}"
    user_answer = st.session_state.get(input_key)

    # 2. 유효성 검사 (값이 없으면 경고 표시 후 중단)
    if user_answer is None or user_answer == "":
        st.session_state.submit_warning = "앗, 답변을 선택하거나 입력해주세요! 🤔"
        return

    # 3. 값이 있으면 경고 초기화 및 로직 진행
    st.session_state.submit_warning = None

    # 정답 여부 판단
    is_correct = (str(user_answer) == str(correct_answer))

    # 로그 기록
    log_event(st.session_state.session_id, st.session_state.user_id, problem_id, 'SUBMIT', 'submit_button', user_answer,
              is_correct)

    # 정답 저장
    current_idx = st.session_state.current_problem
    st.session_state.answers[current_idx] = user_answer

    # 상태 업데이트 (다음 문제로 이동)
    st.session_state.current_problem += 1

    # [중요] 다음 문제로 넘어가므로 문제별 상태 초기화
    st.session_state.show_hint_current = False


# --- 2. 앱 상태 초기화 ---

challenges = load_challenges()
total_problems = len(challenges)

if 'current_problem' not in st.session_state:
    st.session_state.current_problem = 0
    st.session_state.session_id = f"sess_{int(datetime.now().timestamp())}"
    st.session_state.user_id = f"user_{int(datetime.now().timestamp())}"
    st.session_state.answers = [None] * total_problems

    st.session_state.start_time = datetime.now()
    st.session_state.hint_clicks = 0

    # [NEW] UI 제어용 상태 변수
    st.session_state.show_hint_current = False  # 힌트가 켜져있는지 확인
    st.session_state.submit_warning = None  # 제출 시 경고 메시지 저장

    # log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'start') # UptimeMonitorBot Block

# --- 3. 애플리케이션 UI 렌더링 ---

st.title("🧠 인지 프로파일링 챌린지")

# 3.1. 사용자 정보 수집 화면
if 'demographics_submitted' not in st.session_state:
    st.info("챌린지에 참여해주셔서 감사합니다! 💡")

    with st.form(key='demographics_form'):
        st.subheader("🎁 챌린지 완료 감사 기프티콘!\n(노트를 준비하시면 더 편하게 테스트 하실 수 있어요! 😎)")
        st.markdown("참여해주신 분들 중 추첨을 통해 기프티콘을 드립니다. (선택사항)")
        email = st.text_input("이메일 (기프티콘 추첨용)", placeholder="example@gmail.com")

        st.divider()

        st.markdown("**더 나은 연구를 위해, 괜찮으시다면 아래 정보도 제공해주세요. (선택사항)**")
        age = st.selectbox("연령대를 선택해주세요.", ["선택 안 함", "10대", "20대", "30대", "40대 이상"])
        gender = st.selectbox("성별을 선택해주세요.", ["선택 안 함", "남성", "여성", "기타"])
        education = st.selectbox("최종 학력을 선택해주세요.", ["선택 안 함", "중/고등학생", "대학생", "대학원생", "기타"])

        if st.form_submit_button("챌린지 시작하기"):
            log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'start')
            user_info = {
                "email": email,
                "age": age,
                "gender": gender,
                "education": education
            }
            log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SURVEY', 'submit_demographics',
                      value_1=user_info)
            st.session_state.demographics_submitted = True
            st.rerun()

# --- 3.2. 챌린지 진행 화면 ---
elif st.session_state.current_problem < total_problems:
    st.progress(st.session_state.current_problem / total_problems)

    problem_index = st.session_state.current_problem
    problem = challenges[problem_index]
    problem_id = problem['id']

    st.header(f"Part {problem_id[0]}: {problem['part']}")
    st.subheader(f"Question {problem_index + 1}/{total_problems}")
    st.markdown(problem['question'])

    # 입력 위젯 생성
    answer_type = problem.get('answer_type', 'text_input')
    if answer_type == 'text_input':
        st.text_input("정답:", key=f"answer_{problem_id}")
    elif answer_type == 'multiple_choice':
        st.radio("선택:", options=problem['options'], key=f"answer_{problem_id}", index=None)

    # 경고 메시지 표시 (콜백에서 설정됨)
    if st.session_state.submit_warning:
        st.error(st.session_state.submit_warning)

    # 힌트 메시지 표시 (콜백에서 설정됨)
    if st.session_state.show_hint_current:
        st.info(problem['hint'])

    col1, col2 = st.columns([1, 1])

    # [NEW] 버튼 - on_click 사용
    # 힌트 버튼
    col1.button(
        "힌트 보기",
        key=f"hint_btn_{problem_id}",
        on_click=handle_hint,
        args=(problem_id,)  # 튜플로 전달
    )

    # 다음 문제 버튼
    col2.button(
        "다음 문제로",
        key=f"submit_btn_{problem_id}",
        on_click=handle_submit,
        args=(problem_id, problem['correct_answer'])
    )

# --- 3.3. 챌린지 완료 화면 ---
else:
    # 3. [수정] 완료 메시지를 Toast(일시적 팝업)로 변경
    # 세션이 처음 종료되는 시점에만 실행
    if 'session_ended' not in st.session_state:
        st.toast("챌린지를 완료했습니다! 당신의 문제 해결 스타일을 분석해봤어요.", icon="🎉")
        st.balloons()

        end_time = datetime.now()
        total_duration_seconds = (end_time - st.session_state.start_time).total_seconds()
        st.session_state.total_duration = total_duration_seconds

        log_event(st.session_state.session_id, st.session_state.user_id, 'N/A', 'SESSION', 'end',
                  value_1=total_duration_seconds)
        st.session_state.session_ended = True

    # 1. 통계 계산
    correct_answers = sum(
        1 for i, ans in enumerate(st.session_state.answers) if str(ans) == str(challenges[i]['correct_answer']))
    correct_rate = correct_answers / total_problems
    total_time = st.session_state.get('total_duration', 300)
    hint_count = st.session_state.get('hint_clicks', 0)

    # 2. 페르소나 판별
    persona_type = "균형잡힌 해결사"
    TIME_THRESHOLD_FAST = 180;
    TIME_THRESHOLD_SLOW = 420
    ACCURACY_THRESHOLD_HIGH = 0.77;
    ACCURACY_THRESHOLD_LOW = 0.44

    if total_time < TIME_THRESHOLD_FAST and correct_rate >= ACCURACY_THRESHOLD_HIGH:
        persona_type = "신속한 전략가"
    elif total_time > TIME_THRESHOLD_SLOW and correct_rate >= ACCURACY_THRESHOLD_HIGH:
        persona_type = "신중한 탐험가"
    elif total_time < TIME_THRESHOLD_FAST and correct_rate < ACCURACY_THRESHOLD_HIGH:
        persona_type = "직관적인 해결사"
    elif correct_rate <= ACCURACY_THRESHOLD_LOW or (
            total_time > TIME_THRESHOLD_SLOW and correct_rate < ACCURACY_THRESHOLD_HIGH):
        persona_type = "성실한 등반가"

    persona_descriptions = {
        "신속한 전략가": {"icon": "⚡️", "desc": "핵심을 빠르게 파악하고 효율적으로 해결합니다.", "action": "빠른 속도 속 놓치는 게 없는지 한 번 더 확인해보세요."},
        "신중한 탐험가": {"icon": "🗺️", "desc": "돌다리도 두들겨 보며 가장 확실한 길을 찾습니다.", "action": "가끔은 직관을 믿고 과감하게 시도해보세요."},
        "직관적인 해결사": {"icon": "💡", "desc": "번뜩이는 직관과 창의력으로 접근합니다.", "action": "직관에 논리적 검증을 더하면 완벽합니다."},
        "성실한 등반가": {"icon": "🧗", "desc": "쉽게 포기하지 않는 끈기로 문제를 해결합니다.", "action": "핵심 원리를 파악하는 연습이 큰 도움이 될 거예요."},
        "균형잡힌 해결사": {"icon": "⚖️", "desc": "속도와 정확성의 균형이 잘 잡혀 있습니다.", "action": "다양한 전략을 상황에 맞게 사용하는 연습을 해보세요."}
    }

    # UI 렌더링: 분석 결과 텍스트
    st.divider()
    details = persona_descriptions.get(persona_type)
    if details:
        st.markdown(f"### {details['icon']} 당신의 문제 해결 스타일은: **{persona_type}**")
        st.markdown(f"> _{details['desc']}_")

        evidence_text = (f"당신은 **약 {total_time:.0f}초** 동안 **{correct_answers}문제**를 맞혔고, "
                         f"**{hint_count}번**의 힌트를 사용했습니다.")
        st.info(f"**📊 분석 근거:**\n{evidence_text}")
        st.warning(f"**💡 성장 팁:**\n{details['action']}")

    # --- [수정] 결과 이미지 즉시 표시 ---
    st.divider()
    st.subheader("💌 나의 결과 카드")

    # 이미지 생성 데이터 준비
    details["name"] = persona_type
    stats_data = {"correct_rate": correct_rate, "total_time": total_time, "hint_count": hint_count}

    # 이미지 생성 및 즉시 출력
    image_bytes = create_result_image(details, stats_data)
    st.image(image_bytes, caption="아래 버튼을 눌러 이미지를 저장하세요!")

    # 다운로드 버튼
    st.download_button(
        label="결과 이미지 저장하기 📥",
        data=image_bytes,
        file_name=f"my_persona_{persona_type}.png",
        mime="image/png"
    )

    # 분석 설명 (Expander)
    st.divider()
    with st.expander("👀 이 분석 결과는 어떻게 만들어졌나요?"):
        st.markdown("규칙 기반 가이드라인에 따라 제공됩니다. 데이터가 쌓이면 머신러닝 모델로 보다 더 고도화될 예정입니다.")

    st.divider()
    st.subheader("🔗 친구에게 테스트 공유하기")
    share_url = "https://project-insight-nfusfp3ngjmee73ad9jxh9.streamlit.app/"

    st.write("아래 주소 우측의 **복사 버튼(📄)**을 눌러 공유하세요!")
    st.code(share_url, language="text")