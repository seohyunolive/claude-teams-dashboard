"""
Claude Teams 관리자 대시보드
Streamlit 기반 웹 애플리케이션
다중 스냅샷 관리 지원
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from data_loader import DataLoader, DashboardData, load_cumulative_data
from analytics import UsageAnalytics, SnapshotComparison
from visualizations import DashboardCharts

# 페이지 설정
st.set_page_config(
    page_title="Claude Teams 관리자 대시보드",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 비밀번호 인증
# ============================================================
def check_password():
    """비밀번호 인증 체크"""

    # 비밀번호 설정 (원하는 비밀번호로 변경하세요)
    CORRECT_PASSWORD = "claudeai"

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # 로그인 화면
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 2rem;
            background-color: #f8f9fa;
            border-radius: 10px;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("## 🔒 Claude Teams 대시보드")
        st.markdown("접근하려면 비밀번호를 입력하세요.")
        st.markdown("")

        password = st.text_input("비밀번호", type="password", key="password_input")

        if st.button("로그인", type="primary", use_container_width=True):
            if password == CORRECT_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")

        st.markdown("")
        st.caption("문의: 관리자에게 연락하세요")

    return False

# 인증 체크 - 인증 안되면 여기서 중단
if not check_password():
    st.stop()

# ============================================================

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 0.75rem;
        border-radius: 8px;
    }
    /* 사이드바 metric 크기 조정 */
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
    }
    /* 사이드바 여백 조정 */
    [data-testid="stSidebar"] .stSelectbox {
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 기능 플래그
# ============================================================
SHOW_CONVERSATION_TAB = False  # 대화 조회 탭 표시 여부 (개인정보 보호를 위해 기본값 False)

# 세션 상태 초기화
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.data = None
    st.session_state.snapshot_list = []


@st.cache_data(ttl=3600)
def load_data_cached(data_path: str) -> DashboardData:
    """캐시된 데이터 로드"""
    loader = DataLoader(data_path)
    return loader.load_all()


# ============================================================
# 내장 데이터 자동 로드 (GitHub/Streamlit Cloud용)
# ============================================================
def get_embedded_data_path():
    """내장 데이터 경로 반환 (앱과 같은 폴더의 data 디렉토리)"""
    return Path(__file__).parent / "data"

def find_embedded_snapshots():
    """내장 데이터에서 스냅샷 폴더 찾기"""
    data_path = get_embedded_data_path()
    if not data_path.exists():
        return []

    snapshots = []
    for folder in data_path.iterdir():
        if folder.is_dir():
            if (folder / "users.json").exists() and (folder / "conversations.json").exists():
                snapshots.append(folder.name)

    return sorted(snapshots, reverse=True)

# 시작 시 내장 데이터 자동 로드
if not st.session_state.data_loaded:
    embedded_snapshots = find_embedded_snapshots()
    if embedded_snapshots:
        st.session_state.snapshot_list = embedded_snapshots
        # 최신 스냅샷 자동 로드
        latest_snapshot = embedded_snapshots[0]
        try:
            snapshot_path = get_embedded_data_path() / latest_snapshot
            st.session_state.data = load_data_cached(str(snapshot_path))
            st.session_state.data_loaded = True
        except Exception:
            pass

# ============================================================
# 사이드바: 스냅샷 선택
# ============================================================
st.sidebar.title("📊 대시보드")

embedded_snapshots = find_embedded_snapshots()

if embedded_snapshots:
    # 현재 선택된 스냅샷 추적
    if 'current_snapshot' not in st.session_state:
        st.session_state.current_snapshot = embedded_snapshots[0]

    selected_snapshot = st.sidebar.selectbox(
        "📁 스냅샷",
        options=embedded_snapshots,
        index=embedded_snapshots.index(st.session_state.current_snapshot) if st.session_state.current_snapshot in embedded_snapshots else 0,
        help="날짜순으로 정렬됨 (최신순)"
    )

    # 스냅샷 변경 시 자동 로드
    if selected_snapshot != st.session_state.get('current_snapshot'):
        try:
            snapshot_path = get_embedded_data_path() / selected_snapshot
            st.session_state.data = load_data_cached(str(snapshot_path))
            st.session_state.data_loaded = True
            st.session_state.current_snapshot = selected_snapshot
            st.session_state.show_comparison = False  # 비교 모드 초기화
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"로드 실패: {e}")

    # 스냅샷 비교 옵션 (2개 이상일 때만)
    if len(embedded_snapshots) >= 2:
        st.sidebar.divider()

        with st.sidebar.expander("🔄 스냅샷 비교", expanded=False):
            compare_snapshot = st.selectbox(
                "비교 대상",
                options=[s for s in embedded_snapshots if s != selected_snapshot],
                key="compare_snapshot",
                help="현재 스냅샷과 비교할 이전 스냅샷"
            )

            if st.button("비교 분석 실행", type="primary", use_container_width=True):
                try:
                    with st.spinner("분석 중..."):
                        prev_path = get_embedded_data_path() / compare_snapshot
                        prev_data = load_data_cached(str(prev_path))

                        curr_path = get_embedded_data_path() / selected_snapshot
                        curr_data = load_data_cached(str(curr_path))

                        if prev_data and curr_data:
                            st.session_state.comparison = SnapshotComparison(prev_data, curr_data)
                            st.session_state.show_comparison = True
                            st.session_state.data = curr_data
                            st.session_state.data_loaded = True
                            st.rerun()
                except Exception as e:
                    st.error(f"비교 실패: {e}")
else:
    st.sidebar.warning("데이터가 없습니다. 관리자에게 문의하세요.")

# 데이터 로드 상태 표시
if st.session_state.data_loaded:
    data = st.session_state.data
    st.sidebar.divider()
    st.sidebar.caption("현재 데이터")
    col1, col2, col3 = st.sidebar.columns(3)
    col1.metric("사용자", f"{len(data.users)}")
    col2.metric("대화", f"{len(data.conversations)}")
    col3.metric("메시지", f"{len(data.messages)}")


# ============================================================
# 메인 콘텐츠
# ============================================================
st.markdown('<p class="main-header">🤖 Claude Teams 관리자 대시보드</p>', unsafe_allow_html=True)

if not st.session_state.data_loaded:
    st.info("👈 사이드바에서 스냅샷을 선택하세요.")
    st.stop()

# 데이터 분석 객체 생성
analytics = UsageAnalytics(st.session_state.data)

# 탭 구성 - 현황 / 사용 추이 / 사용자 상세 / 누적 현황 / 스냅샷 비교
tab_names = ["📊 전체 현황", "📈 사용 추이"]
if SHOW_CONVERSATION_TAB:
    tab_names.append("💬 대화 조회")
tab_names.append("👤 사용자 상세")
tab_names.append("📚 누적 현황")
if st.session_state.get('show_comparison') and st.session_state.get('comparison'):
    tab_names.append("🔄 스냅샷 비교")

tabs = st.tabs(tab_names)
tab_idx = 0

tab1 = tabs[tab_idx]; tab_idx += 1
tab2 = tabs[tab_idx]; tab_idx += 1
tab3 = tabs[tab_idx] if SHOW_CONVERSATION_TAB else None
if SHOW_CONVERSATION_TAB:
    tab_idx += 1
tab4 = tabs[tab_idx]; tab_idx += 1
tab_cumulative = tabs[tab_idx]; tab_idx += 1
tab5 = tabs[tab_idx] if st.session_state.get('show_comparison') and st.session_state.get('comparison') else None


# ============================================================
# TAB 1: 전체 현황
# ============================================================
with tab1:
    st.header("전체 사용량 현황")

    user_summary = analytics.get_user_summary()
    overall_stats = analytics.get_overall_stats()

    # KPI 메트릭
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="총 사용자",
            value=f"{overall_stats['total_users']}명"
        )

    with col2:
        st.metric(
            label="총 대화 수",
            value=f"{overall_stats['total_conversations']}개"
        )

    with col3:
        st.metric(
            label="총 메시지 수",
            value=f"{overall_stats['total_messages']:,}개"
        )

    with col4:
        avg_msgs = overall_stats['avg_messages_per_user']
        st.metric(
            label="평균 메시지/사용자",
            value=f"{avg_msgs:.1f}개"
        )

    st.divider()

    # 차트 영역
    col_left, col_right = st.columns(2)

    with col_left:
        fig_bar = DashboardCharts.user_usage_bar(user_summary)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        fig_pie = DashboardCharts.user_pie_chart(user_summary)
        st.plotly_chart(fig_pie, use_container_width=True)

    # 상세 테이블
    st.subheader("사용자별 상세 현황")

    # 표시할 컬럼 설정
    display_df = user_summary.copy()
    column_config = {
        'full_name': '이름',
        'email_address': '이메일',
        'total_conversations': '대화 수',
        'total_messages': '총 메시지'
    }

    display_cols = ['full_name', 'email_address', 'total_conversations', 'total_messages']

    if 'human' in display_df.columns:
        display_cols.append('human')
        column_config['human'] = '사용자 메시지'
    if 'assistant' in display_df.columns:
        display_cols.append('assistant')
        column_config['assistant'] = 'Claude 응답'

    st.dataframe(
        display_df[display_cols].rename(columns=column_config),
        use_container_width=True,
        hide_index=True
    )

    # CSV 다운로드
    csv = display_df[display_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 CSV 다운로드",
        data=csv,
        file_name="claude_teams_usage_summary.csv",
        mime="text/csv"
    )


# ============================================================
# TAB 2: 사용 추이
# ============================================================
with tab2:
    st.header("기간별 사용량 추이")

    # 기간 선택
    col1, col2 = st.columns(2)

    with col1:
        date_range = overall_stats['date_range']
        min_date = date_range['start'].date() if date_range['start'] else datetime.now().date() - timedelta(days=30)
        max_date = date_range['end'].date() if date_range['end'] else datetime.now().date()

        selected_range = st.date_input(
            "조회 기간",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            help="시작일과 종료일을 선택하세요"
        )

    with col2:
        view_type = st.selectbox(
            "집계 단위",
            ["일별", "주별"]
        )

    st.divider()

    # 차트 표시
    if view_type == "일별":
        daily_df = analytics.get_daily_usage()

        if len(daily_df) > 0:
            # 선택 기간 필터링
            if len(selected_range) == 2:
                start, end = selected_range
                daily_df = daily_df[
                    (daily_df['date'] >= start) &
                    (daily_df['date'] <= end)
                ]

            fig_trend = DashboardCharts.daily_trend_line(daily_df)
            st.plotly_chart(fig_trend, use_container_width=True)

            # 대화 생성 타임라인
            conv_df = analytics.conversations
            fig_conv = DashboardCharts.conversation_timeline(conv_df)
            st.plotly_chart(fig_conv, use_container_width=True)

            # 상세 데이터 테이블
            with st.expander("📋 상세 데이터 보기"):
                st.dataframe(
                    daily_df.rename(columns={
                        'date': '날짜',
                        'messages': '메시지 수',
                        'active_users': '활성 사용자'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("표시할 데이터가 없습니다.")

    else:  # 주별
        weekly_df = analytics.get_weekly_usage()

        if len(weekly_df) > 0:
            fig_weekly = DashboardCharts.weekly_bar_chart(weekly_df)
            st.plotly_chart(fig_weekly, use_container_width=True)

            with st.expander("📋 상세 데이터 보기"):
                st.dataframe(
                    weekly_df.rename(columns={
                        'year': '연도',
                        'week': '주차',
                        'messages': '메시지 수',
                        'active_users': '활성 사용자'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.warning("표시할 데이터가 없습니다.")


# ============================================================
# TAB 3: 대화 조회 (SHOW_CONVERSATION_TAB=True일 때만 표시)
# ============================================================
if SHOW_CONVERSATION_TAB and tab3 is not None:
    with tab3:
        st.header("대화 내용 조회/검색")

        # 검색 필터
        col1, col2 = st.columns([2, 1])

        with col1:
            search_query = st.text_input(
                "🔍 검색어",
                placeholder="대화 내용에서 검색할 키워드를 입력하세요"
            )

        with col2:
            user_options = ['전체'] + analytics.users['full_name'].tolist()
            user_filter = st.selectbox(
                "사용자 필터",
                options=user_options
            )

        st.divider()

        # 검색 실행
        if search_query:
            user_uuid = None
            if user_filter != '전체':
                user_uuid = analytics.users[
                    analytics.users['full_name'] == user_filter
                ]['user_uuid'].iloc[0]

            results = analytics.search_conversations(search_query, user_uuid)

            st.write(f"**검색 결과: {len(results)}건**")

            if len(results) > 0:
                for idx, row in results.head(50).iterrows():
                    sender_label = '👤 사용자' if row['sender'] == 'human' else '🤖 Claude'
                    time_str = row['created_at'].strftime('%Y-%m-%d %H:%M')

                    with st.expander(f"{row['full_name']} | {sender_label} | {time_str}"):
                        st.markdown(f"**발신자**: {sender_label}")
                        st.markdown(f"**시간**: {time_str}")
                        st.divider()

                        # 텍스트 미리보기 (긴 경우 자르기)
                        text = row['text']
                        if len(text) > 1000:
                            st.markdown(text[:1000] + "...")
                            if st.button(f"전체 보기 ({len(text)}자)", key=f"full_{idx}"):
                                st.markdown(text)
                        else:
                            st.markdown(text if text else "(내용 없음)")
            else:
                st.info("검색 결과가 없습니다.")

        else:
            # 최근 대화 목록
            st.subheader("최근 대화 목록")

            recent_convs = analytics.conversations.sort_values('updated_at', ascending=False).head(20)
            recent_convs = recent_convs.merge(
                analytics.users[['user_uuid', 'full_name']],
                on='user_uuid',
                how='left'
            )

            for _, conv in recent_convs.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    conv_name = conv['name'] if conv['name'] else '(제목 없음)'
                    st.write(f"**{conv_name}**")
                    st.caption(f"👤 {conv['full_name']}")

                with col2:
                    st.write(f"💬 {conv['message_count']}개")

                with col3:
                    st.caption(conv['updated_at'].strftime('%Y-%m-%d'))

                # 대화 상세 보기
                with st.expander("대화 내용 보기"):
                    msgs = analytics.get_conversation_messages(conv['conv_uuid'])
                    for _, msg in msgs.iterrows():
                        sender_icon = '👤' if msg['sender'] == 'human' else '🤖'
                        st.markdown(f"**{sender_icon} {msg['sender']}** ({msg['created_at'].strftime('%H:%M')})")
                        text = msg['text'][:500] + "..." if len(msg['text']) > 500 else msg['text']
                        st.markdown(text if text else "(내용 없음)")
                        st.divider()

                st.divider()


# ============================================================
# TAB 4: 사용자 상세
# ============================================================
with tab4:
    st.header("사용자별 상세 분석")

    selected_user = st.selectbox(
        "사용자 선택",
        options=analytics.users['full_name'].tolist(),
        key='user_select'
    )

    if selected_user:
        user_row = analytics.users[analytics.users['full_name'] == selected_user].iloc[0]
        user_uuid = user_row['user_uuid']

        user_detail = analytics.get_user_detail(user_uuid)

        # 사용자 정보 카드
        st.subheader(f"👤 {user_row['full_name']}")
        st.write(f"📧 {user_row['email_address']}")

        if pd.notna(user_row.get('verified_phone_number')):
            st.write(f"📱 {user_row['verified_phone_number']}")

        st.divider()

        # 메트릭
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("총 대화", f"{user_detail['total_conversations']}개")
        with col2:
            st.metric("총 메시지", f"{user_detail['total_messages']}개")
        with col3:
            st.metric("사용자 메시지", f"{user_detail['human_messages']}개")
        with col4:
            st.metric("대화당 평균", f"{user_detail['avg_messages_per_conv']:.1f}개")

        st.divider()

        # 활동 기간
        col1, col2 = st.columns(2)

        with col1:
            if user_detail['first_activity']:
                st.write(f"🕐 **첫 활동**: {user_detail['first_activity'].strftime('%Y-%m-%d %H:%M')}")
            else:
                st.write("🕐 **첫 활동**: -")

        with col2:
            if user_detail['last_activity']:
                st.write(f"🕐 **최근 활동**: {user_detail['last_activity'].strftime('%Y-%m-%d %H:%M')}")
            else:
                st.write("🕐 **최근 활동**: -")

        st.divider()

        # 메시지 유형 차트
        if user_detail['total_messages'] > 0:
            fig_msg_type = DashboardCharts.message_type_breakdown(
                user_detail['human_messages'],
                user_detail['assistant_messages']
            )
            st.plotly_chart(fig_msg_type, use_container_width=True)

        # 사용자의 대화 목록 (개인정보 보호를 위해 숨김 처리)
        # st.subheader("대화 목록")
        #
        # if user_detail['conversations']:
        #     conv_df = pd.DataFrame(user_detail['conversations'])
        #
        #     st.dataframe(
        #         conv_df[['name', 'message_count', 'created_at', 'updated_at']].rename(columns={
        #             'name': '대화 제목',
        #             'message_count': '메시지 수',
        #             'created_at': '생성일',
        #             'updated_at': '최근 활동'
        #         }),
        #         use_container_width=True,
        #         hide_index=True
        #     )
        # else:
        #     st.info("대화 내역이 없습니다.")


# ============================================================
# TAB: 누적 현황
# ============================================================
with tab_cumulative:
    st.header("전체 누적 현황")

    # 누적 데이터 로드 (캐시 사용)
    @st.cache_data(ttl=3600)
    def get_cumulative_data():
        return load_cumulative_data(str(get_embedded_data_path()))

    cumulative_data = get_cumulative_data()

    if cumulative_data is None:
        st.warning("누적 데이터를 로드할 수 없습니다.")
    else:
        cumulative_analytics = UsageAnalytics(cumulative_data)

        # 조회 기간 및 집계 단위 설정
        st.subheader("조회 설정")
        col1, col2 = st.columns(2)

        with col1:
            cumulative_stats = cumulative_analytics.get_overall_stats()
            date_range = cumulative_stats['date_range']
            min_date = date_range['start'].date() if date_range['start'] else datetime.now().date() - timedelta(days=365)
            max_date = date_range['end'].date() if date_range['end'] else datetime.now().date()

            cumulative_date_range = st.date_input(
                "조회 기간",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                help="시작일과 종료일을 선택하세요",
                key="cumulative_date_range"
            )

        with col2:
            cumulative_view_type = st.selectbox(
                "집계 단위",
                ["일별", "주별", "월별"],
                key="cumulative_view_type"
            )

        st.divider()

        # KPI 메트릭 (전체 누적)
        st.subheader("전체 누적 통계")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="총 사용자",
                value=f"{cumulative_stats['total_users']}명"
            )

        with col2:
            st.metric(
                label="총 대화 수",
                value=f"{cumulative_stats['total_conversations']}개"
            )

        with col3:
            st.metric(
                label="총 메시지 수",
                value=f"{cumulative_stats['total_messages']:,}개"
            )

        with col4:
            avg_msgs = cumulative_stats['avg_messages_per_user']
            st.metric(
                label="평균 메시지/사용자",
                value=f"{avg_msgs:.1f}개"
            )

        st.divider()

        # 기간별 사용량 추이
        st.subheader("기간별 사용량 추이")

        if cumulative_view_type == "일별":
            daily_df = cumulative_analytics.get_daily_usage()

            if len(daily_df) > 0:
                # 선택 기간 필터링
                if len(cumulative_date_range) == 2:
                    start, end = cumulative_date_range
                    daily_df = daily_df[
                        (daily_df['date'] >= start) &
                        (daily_df['date'] <= end)
                    ]

                fig_trend = DashboardCharts.daily_trend_line(daily_df)
                st.plotly_chart(fig_trend, use_container_width=True, key="cumulative_daily_chart")

                with st.expander("📋 상세 데이터 보기", expanded=False):
                    st.dataframe(
                        daily_df.rename(columns={
                            'date': '날짜',
                            'messages': '메시지 수',
                            'active_users': '활성 사용자'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        key="cumulative_daily_df"
                    )
            else:
                st.warning("표시할 데이터가 없습니다.")

        elif cumulative_view_type == "주별":
            weekly_df = cumulative_analytics.get_weekly_usage()

            if len(weekly_df) > 0:
                fig_weekly = DashboardCharts.weekly_bar_chart(weekly_df)
                st.plotly_chart(fig_weekly, use_container_width=True, key="cumulative_weekly_chart")

                with st.expander("📋 상세 데이터 보기", expanded=False):
                    st.dataframe(
                        weekly_df.rename(columns={
                            'year': '연도',
                            'week': '주차',
                            'messages': '메시지 수',
                            'active_users': '활성 사용자'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        key="cumulative_weekly_df"
                    )
            else:
                st.warning("표시할 데이터가 없습니다.")

        else:  # 월별
            # 월별 집계
            messages_df = cumulative_analytics.messages.copy()
            if len(messages_df) > 0:
                messages_df['month'] = messages_df['created_at'].dt.to_period('M')
                monthly_df = messages_df.groupby('month').agg(
                    messages=('msg_uuid', 'count'),
                    active_users=('user_uuid', 'nunique')
                ).reset_index()
                monthly_df['month'] = monthly_df['month'].astype(str)

                # 월별 차트
                import plotly.express as px
                fig_monthly = px.bar(
                    monthly_df,
                    x='month',
                    y='messages',
                    title='월별 메시지 수',
                    labels={'month': '월', 'messages': '메시지 수'}
                )
                fig_monthly.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_monthly, use_container_width=True, key="cumulative_monthly_chart")

                with st.expander("📋 상세 데이터 보기", expanded=False):
                    st.dataframe(
                        monthly_df.rename(columns={
                            'month': '월',
                            'messages': '메시지 수',
                            'active_users': '활성 사용자'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        key="cumulative_monthly_df"
                    )
            else:
                st.warning("표시할 데이터가 없습니다.")

        st.divider()

        # 사용자별 누적 현황
        st.subheader("사용자별 누적 현황")
        cumulative_user_summary = cumulative_analytics.get_user_summary()

        # 표시할 컬럼 설정
        display_df = cumulative_user_summary.copy()
        column_config = {
            'full_name': '이름',
            'email_address': '이메일',
            'total_conversations': '대화 수',
            'total_messages': '총 메시지'
        }

        display_cols = ['full_name', 'email_address', 'total_conversations', 'total_messages']

        if 'human' in display_df.columns:
            display_cols.append('human')
            column_config['human'] = '사용자 메시지'
        if 'assistant' in display_df.columns:
            display_cols.append('assistant')
            column_config['assistant'] = 'Claude 응답'

        st.dataframe(
            display_df[display_cols].rename(columns=column_config),
            use_container_width=True,
            hide_index=True,
            key="cumulative_user_summary_df"
        )

        # CSV 다운로드
        csv = display_df[display_cols].to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 누적 데이터 CSV 다운로드",
            data=csv,
            file_name="claude_teams_cumulative_usage.csv",
            mime="text/csv",
            key="cumulative_csv_download"
        )


# ============================================================
# TAB 5: 스냅샷 비교 (조건부)
# ============================================================
if tab5 is not None:
    with tab5:
        st.header("🔄 스냅샷 비교 분석")

        comparison = st.session_state.comparison

        # 비교 대상 표시
        st.info(f"📊 **{comparison.snapshot1_name}** → **{comparison.snapshot2_name}** 비교")

        # 전체 통계 비교
        st.subheader("전체 통계 변화")
        comp_stats = comparison.compare_overall_stats()

        col1, col2, col3 = st.columns(3)

        with col1:
            change = comp_stats['users']['change']
            st.metric(
                label="총 사용자",
                value=f"{comp_stats['users']['after']}명",
                delta=f"{change:+d}명" if change != 0 else "변동 없음"
            )

        with col2:
            change = comp_stats['conversations']['change']
            change_pct = comp_stats['conversations']['change_pct']
            st.metric(
                label="총 대화 수",
                value=f"{comp_stats['conversations']['after']}개",
                delta=f"{change:+d}개 ({change_pct:+.1f}%)" if change != 0 else "변동 없음"
            )

        with col3:
            change = comp_stats['messages']['change']
            change_pct = comp_stats['messages']['change_pct']
            st.metric(
                label="총 메시지 수",
                value=f"{comp_stats['messages']['after']:,}개",
                delta=f"{change:+,}개 ({change_pct:+.1f}%)" if change != 0 else "변동 없음"
            )

        st.divider()

        # 사용자별 변화
        st.subheader("사용자별 사용량 변화")
        user_comp = comparison.compare_user_summary()

        # 변화량 기준 정렬
        user_comp_sorted = user_comp.sort_values('messages_change', ascending=False)

        display_cols = ['full_name', 'total_messages', 'total_messages_prev', 'messages_change', 'messages_change_pct']
        col_names = {
            'full_name': '이름',
            'total_messages': '현재 메시지',
            'total_messages_prev': '이전 메시지',
            'messages_change': '변화량',
            'messages_change_pct': '변화율(%)'
        }

        st.dataframe(
            user_comp_sorted[display_cols].rename(columns=col_names),
            use_container_width=True,
            hide_index=True
        )

        # 신규 사용자
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🆕 신규 사용자")
            new_users = comparison.get_new_users()
            if len(new_users) > 0:
                st.dataframe(
                    new_users[['full_name', 'email_address']].rename(columns={
                        'full_name': '이름',
                        'email_address': '이메일'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("신규 사용자 없음")

        with col2:
            st.subheader("😴 비활성 사용자")
            inactive_users = comparison.get_inactive_users()
            if len(inactive_users) > 0:
                st.dataframe(
                    inactive_users[['full_name', 'email_address']].rename(columns={
                        'full_name': '이름',
                        'email_address': '이메일'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("비활성 사용자 없음")


# ============================================================
# 푸터
# ============================================================
st.divider()
st.caption("Claude Teams 관리자 대시보드 v1.1 | 다중 스냅샷 지원 | Made with Streamlit")
