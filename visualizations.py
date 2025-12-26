"""
시각화 모듈
Plotly 기반 차트 생성
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


class DashboardCharts:
    """대시보드 차트 생성 클래스"""

    @staticmethod
    def user_usage_bar(df: pd.DataFrame) -> go.Figure:
        """사용자별 사용량 막대 차트"""
        fig = px.bar(
            df.sort_values('total_messages', ascending=True),
            x='total_messages',
            y='full_name',
            orientation='h',
            title='사용자별 총 메시지 수',
            labels={'total_messages': '메시지 수', 'full_name': '사용자'},
            color='total_messages',
            color_continuous_scale='Blues'
        )
        fig.update_layout(
            showlegend=False,
            height=max(300, len(df) * 40),
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    @staticmethod
    def daily_trend_line(df: pd.DataFrame) -> go.Figure:
        """일별 사용량 추이 라인 차트"""
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['messages'],
            mode='lines+markers',
            name='메시지 수',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
        ))

        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['active_users'],
            mode='lines+markers',
            name='활성 사용자 수',
            yaxis='y2',
            line=dict(color='#ff7f0e', width=2),
            marker=dict(size=6)
        ))

        fig.update_layout(
            title='일별 사용량 추이',
            xaxis_title='날짜',
            yaxis=dict(
                title=dict(text='메시지 수', font=dict(color='#1f77b4')),
                side='left'
            ),
            yaxis2=dict(
                title=dict(text='활성 사용자', font=dict(color='#ff7f0e')),
                side='right',
                overlaying='y'
            ),
            hovermode='x unified',
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )

        return fig

    @staticmethod
    def user_pie_chart(df: pd.DataFrame) -> go.Figure:
        """사용자별 사용량 비율 파이 차트"""
        # 사용량이 있는 사용자만 필터
        df_filtered = df[df['total_messages'] > 0]

        fig = px.pie(
            df_filtered,
            values='total_messages',
            names='full_name',
            title='사용자별 메시지 비율',
            hole=0.3
        )
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            textfont_size=11
        )
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.2)
        )
        return fig

    @staticmethod
    def message_type_breakdown(human_count: int, assistant_count: int) -> go.Figure:
        """메시지 유형 분포 막대 차트"""
        fig = go.Figure(data=[go.Bar(
            x=['사용자 메시지', 'Claude 응답'],
            y=[human_count, assistant_count],
            marker_color=['#2ecc71', '#3498db'],
            text=[human_count, assistant_count],
            textposition='auto'
        )])
        fig.update_layout(
            title='메시지 유형 분포',
            xaxis_title='유형',
            yaxis_title='메시지 수',
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    @staticmethod
    def weekly_bar_chart(df: pd.DataFrame) -> go.Figure:
        """주별 사용량 막대 차트"""
        # 연도-주차 라벨 생성
        df = df.copy()
        df['week_label'] = df['year'].astype(str) + '-W' + df['week'].astype(str).str.zfill(2)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df['week_label'],
            y=df['messages'],
            name='메시지 수',
            marker_color='#1f77b4'
        ))

        fig.add_trace(go.Scatter(
            x=df['week_label'],
            y=df['active_users'],
            mode='lines+markers',
            name='활성 사용자',
            yaxis='y2',
            line=dict(color='#ff7f0e', width=2),
            marker=dict(size=8)
        ))

        fig.update_layout(
            title='주별 사용량 추이',
            xaxis_title='주차',
            yaxis=dict(title='메시지 수', side='left'),
            yaxis2=dict(title='활성 사용자', side='right', overlaying='y'),
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            barmode='group'
        )

        return fig

    @staticmethod
    def conversation_timeline(df: pd.DataFrame) -> go.Figure:
        """대화 생성 타임라인"""
        df = df.copy()
        df['date'] = df['created_at'].dt.date

        daily_convs = df.groupby('date').size().reset_index(name='conversations')

        fig = px.area(
            daily_convs,
            x='date',
            y='conversations',
            title='일별 새 대화 수',
            labels={'date': '날짜', 'conversations': '대화 수'}
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
