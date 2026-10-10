"""Private viewer for queued and running episodes."""
import json
from datetime import date

import streamlit as st

from mudo.config import profiles
from mudo.engine import MAX_TURNS, daily_prepare, first_ready, queue, review, start, step, today, transcript
from mudo.services import DemoModel, Model

st.set_page_config(page_title="AI 무한도전 실험실",layout="wide")
st.title("AI 무한도전 실험실")
st.caption("비공식 개인용 가상 예능. 매일 기획안이 쌓이고, 재생하면 사건이 진행됩니다.")
demo = st.sidebar.toggle("모의 실행", value=False,
    help="검색과 LLM을 사용하지 않고 저장·재생 흐름만 확인합니다.")
st.sidebar.caption("실제 실행: BRAVE_API_KEY와 OPENAI_API_KEY 또는 OPENAI_BASE_URL을 설정하세요.")
members = profiles()

with st.sidebar:
    st.subheader("오늘의 기획")
    day = st.date_input("기획 날짜",value=date.fromisoformat(today())).isoformat()
    if st.button("소재 검색 후 기획안 저장",use_container_width=True):
        try:
            ep = daily_prepare(day,DemoModel() if demo else Model(),demo=demo)
            st.success(f"기획안 저장: {json.loads(ep['plan'])['title']}")
        except Exception as exc:
            st.error(str(exc))

items = queue()
ready = first_ready()
left,right = st.columns([1,2])
with left:
    st.subheader("기획안 대기열")
    for item in items:
        plan = json.loads(item["plan"])
        st.write(f"**#{item['id']} · {item['day']} · {plan['title']}**")
        st.caption(f"{item['status']} · {item['turn']}/{MAX_TURNS}턴")
        if item['status'] in ('queued','running'):
            with st.expander("기획안"):
                st.write(plan["premise"])
                st.write("첫 상황:",plan["start"])
                st.write("완료 조건:",plan["finish"])
                st.caption("출처: " + plan["source"]["url"])
                if plan["source"]["nm_mode"] == "untrained":
                    st.caption("학습된 NM 모델 미연결: 출처 점수와 피드백 가중치로 후보를 정렬했습니다.")
    if not items:
        st.info("아직 기획안이 없습니다. 왼쪽에서 오늘의 기획을 만드세요.")

with right:
    st.subheader("재생")
    if items:
        choices = sorted(items,key=lambda e:(0 if ready and e['id']==ready['id'] else 1,-e['id']))
        chosen = st.selectbox("볼 에피소드",choices,
            format_func=lambda e:f"#{e['id']} {json.loads(e['plan'])['title']} ({e['status']})")
        eid = chosen["id"]
        ep, history = transcript(eid)
        plan = json.loads(ep["plan"])
        st.write(f"**{plan['title']}** — {plan['start']}")
        st.progress(ep['turn']/MAX_TURNS,text=f"{ep['turn']}/{MAX_TURNS}턴")
        if ep['status'] in ('queued','running'):
            batch = st.slider("이번에 재생할 턴",1,100,10)
            if st.button("이어 재생",type="primary",use_container_width=True):
                try:
                    eid = start(eid)
                    engine = DemoModel() if demo else Model()
                    for _ in range(min(batch,MAX_TURNS-ep["turn"])):
                        step(eid,engine)
                    st.rerun()
                except Exception as exc:
                    st.error(f"중단한 곳까지 저장됐습니다: {exc}")
        full = st.toggle("처음부터 모두 보기",value=ep['status'] in ('awaiting_review','finished'))
        for row in (history if full else history[-35:]):
            label = ("태호 AI" if row['kind']=='producer' else
                     next((m['name'] for m in members if m['id']==row['speaker']),row['speaker']))
            st.markdown(f"**{row['number']} · {label}** — {row['line']}")
            if row['action']:
                st.caption(row['action'])
        if history:
            lines = [f"# {plan['title']}", f"시작 미션: {plan['start']}", ""]
            for row in history:
                label = ("태호 AI" if row['kind']=='producer' else
                         next((m['name'] for m in members if m['id']==row['speaker']),row['speaker']))
                lines += [f"## {row['number']} · {label}", row['line'], ""]
            st.download_button("이번 편 대본 내려받기", "\n".join(lines),
                               file_name=f"mudo_episode_{eid}.md",mime="text/markdown")
    else:
        st.info("대기 중인 회차가 없습니다. 평가 대기 편이 있다면 아래에서 평가하세요.")

awaiting = [e for e in items if e['status']=='awaiting_review']
if awaiting:
    st.divider()
    st.subheader("회차 평가")
    picked = st.selectbox("완료된 회차",awaiting,
                           format_func=lambda e: f"#{e['id']} {json.loads(e['plan'])['title']}")
    with st.form("review"):
        p_fun = st.slider("태호: 플롯 재미",1,5,3)
        p_sim = st.slider("태호: 프로그램 분위기",1,5,3)
        p_note = st.text_area("태호에게 남길 피드백")
        ratings = {}
        for m in members:
            st.markdown(f"**{m['name']}**")
            a,b = st.columns(2)
            fun = a.slider("재미",1,5,3,key=m['id']+'fun')
            likeness = b.slider("캐릭터 적합성",1,5,3,key=m['id']+'likeness')
            note = st.text_input("다음 편에서 참고할 점",key=m['id']+'note')
            ratings[m['id']] = {"fun":fun,"similarity":likeness,"note":note}
        submitted = st.form_submit_button("평가하고 다음 편으로")
    if submitted:
        try:
            review(picked['id'],p_fun,p_sim,ratings,p_note)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
