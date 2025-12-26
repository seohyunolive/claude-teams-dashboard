"""
사용량 분석 모듈
사용자별, 기간별 사용량 집계 및 분석
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from data_loader import DashboardData


class UsageAnalytics:
    """사용량 분석 클래스"""

    def __init__(self, data: DashboardData):
        self.users = data.users
        self.conversations = data.conversations
        self.messages = data.messages

    def get_user_summary(self) -> pd.DataFrame:
        """사용자별 사용량 요약"""
        # 대화 수 집계
        conv_counts = self.conversations.groupby('user_uuid').agg({
            'conv_uuid': 'count',
            'message_count': 'sum'
        }).rename(columns={
            'conv_uuid': 'total_conversations',
            'message_count': 'total_messages'
        })

        # 메시지 유형별 집계 (human/assistant)
        if len(self.messages) > 0:
            msg_by_sender = self.messages.groupby(['user_uuid', 'sender']).size().unstack(fill_value=0)
        else:
            msg_by_sender = pd.DataFrame()

        # 사용자 정보와 병합
        summary = self.users.merge(
            conv_counts,
            left_on='user_uuid',
            right_index=True,
            how='left'
        )

        if len(msg_by_sender) > 0:
            summary = summary.merge(
                msg_by_sender,
                left_on='user_uuid',
                right_index=True,
                how='left'
            )

        summary = summary.fillna(0)

        # 정수형 변환
        for col in ['total_conversations', 'total_messages']:
            if col in summary.columns:
                summary[col] = summary[col].astype(int)

        if 'human' in summary.columns:
            summary['human'] = summary['human'].astype(int)
        if 'assistant' in summary.columns:
            summary['assistant'] = summary['assistant'].astype(int)

        return summary

    def get_daily_usage(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """일별 사용량 추이"""
        if len(self.messages) == 0:
            return pd.DataFrame(columns=['date', 'messages', 'active_users'])

        df = self.messages.copy()
        df['date'] = df['created_at'].dt.date

        if start_date:
            df = df[df['created_at'] >= start_date]
        if end_date:
            df = df[df['created_at'] <= end_date]

        daily = df.groupby('date').agg({
            'msg_uuid': 'count',
            'user_uuid': 'nunique'
        }).rename(columns={
            'msg_uuid': 'messages',
            'user_uuid': 'active_users'
        })

        return daily.reset_index()

    def get_weekly_usage(self) -> pd.DataFrame:
        """주별 사용량 추이"""
        if len(self.messages) == 0:
            return pd.DataFrame(columns=['year', 'week', 'messages', 'active_users'])

        df = self.messages.copy()
        df['week'] = df['created_at'].dt.isocalendar().week
        df['year'] = df['created_at'].dt.year

        weekly = df.groupby(['year', 'week']).agg({
            'msg_uuid': 'count',
            'user_uuid': 'nunique'
        }).rename(columns={
            'msg_uuid': 'messages',
            'user_uuid': 'active_users'
        })

        return weekly.reset_index()

    def get_user_detail(self, user_uuid: str) -> Dict[str, Any]:
        """특정 사용자 상세 분석"""
        user_convs = self.conversations[self.conversations['user_uuid'] == user_uuid]
        user_msgs = self.messages[self.messages['user_uuid'] == user_uuid]

        human_msgs = user_msgs[user_msgs['sender'] == 'human']
        assistant_msgs = user_msgs[user_msgs['sender'] == 'assistant']

        return {
            'total_conversations': len(user_convs),
            'total_messages': len(user_msgs),
            'human_messages': len(human_msgs),
            'assistant_messages': len(assistant_msgs),
            'first_activity': user_msgs['created_at'].min() if len(user_msgs) > 0 else None,
            'last_activity': user_msgs['created_at'].max() if len(user_msgs) > 0 else None,
            'avg_messages_per_conv': len(user_msgs) / len(user_convs) if len(user_convs) > 0 else 0,
            'conversations': user_convs.to_dict('records')
        }

    def search_conversations(
        self,
        query: str,
        user_uuid: Optional[str] = None
    ) -> pd.DataFrame:
        """대화 내용 검색"""
        if len(self.messages) == 0:
            return pd.DataFrame()

        df = self.messages.copy()

        if user_uuid:
            df = df[df['user_uuid'] == user_uuid]

        # 텍스트 검색 (대소문자 무시)
        mask = df['text'].str.contains(query, case=False, na=False)
        results = df[mask].copy()

        # 사용자 정보 병합
        results = results.merge(
            self.users[['user_uuid', 'full_name']],
            on='user_uuid',
            how='left'
        )

        return results.sort_values('created_at', ascending=False)

    def get_conversation_messages(self, conv_uuid: str) -> pd.DataFrame:
        """특정 대화의 메시지 목록"""
        msgs = self.messages[self.messages['conv_uuid'] == conv_uuid].copy()
        return msgs.sort_values('created_at')

    def get_overall_stats(self) -> Dict[str, Any]:
        """전체 통계"""
        return {
            'total_users': len(self.users),
            'total_conversations': len(self.conversations),
            'total_messages': len(self.messages),
            'avg_messages_per_user': len(self.messages) / len(self.users) if len(self.users) > 0 else 0,
            'avg_messages_per_conv': len(self.messages) / len(self.conversations) if len(self.conversations) > 0 else 0,
            'date_range': {
                'start': self.messages['created_at'].min() if len(self.messages) > 0 else None,
                'end': self.messages['created_at'].max() if len(self.messages) > 0 else None
            }
        }


class SnapshotComparison:
    """스냅샷 간 비교 분석"""

    def __init__(self, data1: 'DashboardData', data2: 'DashboardData'):
        """
        data1: 이전 스냅샷 (기준)
        data2: 최신 스냅샷 (비교 대상)
        """
        self.analytics1 = UsageAnalytics(data1)
        self.analytics2 = UsageAnalytics(data2)
        self.snapshot1_name = data1.snapshot_name
        self.snapshot2_name = data2.snapshot_name

    def compare_overall_stats(self) -> Dict[str, Any]:
        """전체 통계 비교"""
        stats1 = self.analytics1.get_overall_stats()
        stats2 = self.analytics2.get_overall_stats()

        def calc_change(old, new):
            if old == 0:
                return 0 if new == 0 else 100.0
            return ((new - old) / old) * 100

        return {
            'snapshot1': self.snapshot1_name,
            'snapshot2': self.snapshot2_name,
            'users': {
                'before': stats1['total_users'],
                'after': stats2['total_users'],
                'change': stats2['total_users'] - stats1['total_users']
            },
            'conversations': {
                'before': stats1['total_conversations'],
                'after': stats2['total_conversations'],
                'change': stats2['total_conversations'] - stats1['total_conversations'],
                'change_pct': calc_change(stats1['total_conversations'], stats2['total_conversations'])
            },
            'messages': {
                'before': stats1['total_messages'],
                'after': stats2['total_messages'],
                'change': stats2['total_messages'] - stats1['total_messages'],
                'change_pct': calc_change(stats1['total_messages'], stats2['total_messages'])
            }
        }

    def compare_user_summary(self) -> pd.DataFrame:
        """사용자별 사용량 비교"""
        summary1 = self.analytics1.get_user_summary()
        summary2 = self.analytics2.get_user_summary()

        # 두 스냅샷 병합
        merged = summary2.merge(
            summary1[['user_uuid', 'total_conversations', 'total_messages']],
            on='user_uuid',
            how='left',
            suffixes=('', '_prev')
        )

        # 변화량 계산
        merged['conversations_change'] = merged['total_conversations'] - merged['total_conversations_prev'].fillna(0)
        merged['messages_change'] = merged['total_messages'] - merged['total_messages_prev'].fillna(0)

        # 변화율 계산
        merged['messages_change_pct'] = merged.apply(
            lambda row: ((row['total_messages'] - row['total_messages_prev']) / row['total_messages_prev'] * 100)
            if row['total_messages_prev'] > 0 else 0,
            axis=1
        )

        return merged

    def get_new_users(self) -> pd.DataFrame:
        """신규 사용자 (이전 스냅샷에 없던 사용자)"""
        users1_ids = set(self.analytics1.users['user_uuid'])
        users2 = self.analytics2.users

        new_users = users2[~users2['user_uuid'].isin(users1_ids)]
        return new_users

    def get_inactive_users(self) -> pd.DataFrame:
        """비활성 사용자 (이전 스냅샷에는 있지만 최신에는 활동 없음)"""
        # 각 스냅샷에서 메시지를 보낸 사용자
        active_users1 = set(self.analytics1.messages['user_uuid'].unique())
        active_users2 = set(self.analytics2.messages['user_uuid'].unique())

        # 이전에는 활동했지만 최신에는 활동 없는 사용자
        inactive_ids = active_users1 - active_users2

        return self.analytics1.users[self.analytics1.users['user_uuid'].isin(inactive_ids)]
