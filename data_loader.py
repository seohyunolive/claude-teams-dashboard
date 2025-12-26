"""
데이터 로드 및 전처리 모듈
Claude Teams JSON 데이터를 DataFrame으로 변환
다중 스냅샷 관리 지원
"""

import json
import re
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict
from datetime import datetime


@dataclass
class DashboardData:
    """대시보드 데이터 컨테이너"""
    users: pd.DataFrame
    conversations: pd.DataFrame
    messages: pd.DataFrame
    snapshot_name: str = ""  # 스냅샷 이름 (폴더명)
    snapshot_date: Optional[datetime] = None  # 스냅샷 날짜


@dataclass
class MultiSnapshotData:
    """다중 스냅샷 데이터 컨테이너"""
    snapshots: Dict[str, DashboardData] = field(default_factory=dict)
    current_snapshot: Optional[str] = None

    @property
    def current(self) -> Optional[DashboardData]:
        """현재 선택된 스냅샷 반환"""
        if self.current_snapshot and self.current_snapshot in self.snapshots:
            return self.snapshots[self.current_snapshot]
        return None

    @property
    def snapshot_names(self) -> List[str]:
        """스냅샷 이름 목록 (날짜순 정렬)"""
        return sorted(self.snapshots.keys(), reverse=True)

    def get_comparison_data(self, snapshot1: str, snapshot2: str) -> Tuple[Optional[DashboardData], Optional[DashboardData]]:
        """두 스냅샷 비교용 데이터 반환"""
        return self.snapshots.get(snapshot1), self.snapshots.get(snapshot2)


class DataLoader:
    """JSON 데이터 로더"""

    def __init__(self, data_path: str):
        self.data_path = Path(data_path)

    def load_users(self) -> pd.DataFrame:
        """users.json 로드"""
        file_path = self.data_path / "users.json"
        with open(file_path, 'r', encoding='utf-8') as f:
            users = json.load(f)

        df = pd.DataFrame(users)
        df.rename(columns={'uuid': 'user_uuid'}, inplace=True)
        return df

    def load_conversations(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        conversations.json 로드
        Returns:
            - conversations_df: 대화 메타데이터
            - messages_df: 개별 메시지 데이터
        """
        file_path = self.data_path / "conversations.json"
        with open(file_path, 'r', encoding='utf-8') as f:
            conversations = json.load(f)

        conv_records = []
        msg_records = []

        for conv in conversations:
            # 대화 레코드
            user_uuid = conv.get('account', {}).get('uuid', '')
            chat_messages = conv.get('chat_messages', [])

            conv_records.append({
                'conv_uuid': conv.get('uuid', ''),
                'name': conv.get('name', '') or '(제목 없음)',
                'summary': conv.get('summary', ''),
                'created_at': pd.to_datetime(conv.get('created_at')),
                'updated_at': pd.to_datetime(conv.get('updated_at')),
                'user_uuid': user_uuid,
                'message_count': len(chat_messages)
            })

            # 메시지 레코드
            for msg in chat_messages:
                # 메시지 텍스트 추출
                text = msg.get('text', '')
                if not text:
                    # content 배열에서 텍스트 추출
                    content_list = msg.get('content', [])
                    if content_list:
                        texts = [c.get('text', '') for c in content_list if c.get('type') == 'text']
                        text = ' '.join(texts)

                msg_records.append({
                    'msg_uuid': msg.get('uuid', ''),
                    'conv_uuid': conv.get('uuid', ''),
                    'user_uuid': user_uuid,
                    'sender': msg.get('sender', ''),
                    'text': text,
                    'created_at': pd.to_datetime(msg.get('created_at')),
                    'has_attachments': len(msg.get('attachments', [])) > 0,
                    'has_files': len(msg.get('files', [])) > 0
                })

        conversations_df = pd.DataFrame(conv_records)
        messages_df = pd.DataFrame(msg_records)

        return conversations_df, messages_df

    def load_all(self) -> DashboardData:
        """모든 데이터 로드"""
        users = self.load_users()
        conversations, messages = self.load_conversations()

        # 스냅샷 이름과 날짜 추출
        snapshot_name = self.data_path.name
        snapshot_date = self._extract_date_from_folder(snapshot_name)

        return DashboardData(
            users=users,
            conversations=conversations,
            messages=messages,
            snapshot_name=snapshot_name,
            snapshot_date=snapshot_date
        )

    def _extract_date_from_folder(self, folder_name: str) -> Optional[datetime]:
        """폴더명에서 날짜 추출 (예: data-2025-12-24-05-11-01-batch-0000)"""
        # 패턴: YYYY-MM-DD 형식 찾기
        match = re.search(r'(\d{4}-\d{2}-\d{2})', folder_name)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except ValueError:
                pass
        return None


class MultiSnapshotLoader:
    """다중 스냅샷 로더"""

    def __init__(self, base_path: str):
        """
        base_path: 스냅샷 폴더들이 있는 상위 디렉토리
        예: c:/Users/user/Desktop/ (여기에 data-2025-01, data-2025-02 등이 있음)
        """
        self.base_path = Path(base_path)

    def find_snapshot_folders(self) -> List[Path]:
        """스냅샷 폴더 목록 찾기 (users.json이 있는 폴더)"""
        snapshot_folders = []

        if not self.base_path.exists():
            return snapshot_folders

        # 하위 폴더 중 users.json이 있는 폴더 찾기
        for folder in self.base_path.iterdir():
            if folder.is_dir():
                if (folder / "users.json").exists() and (folder / "conversations.json").exists():
                    snapshot_folders.append(folder)

        # 날짜순 정렬 (최신순)
        snapshot_folders.sort(key=lambda x: x.name, reverse=True)
        return snapshot_folders

    def load_all_snapshots(self) -> MultiSnapshotData:
        """모든 스냅샷 로드"""
        multi_data = MultiSnapshotData()
        folders = self.find_snapshot_folders()

        for folder in folders:
            try:
                loader = DataLoader(str(folder))
                data = loader.load_all()
                multi_data.snapshots[folder.name] = data
            except Exception as e:
                print(f"스냅샷 로드 실패 ({folder.name}): {e}")

        # 첫 번째(최신) 스냅샷을 기본 선택
        if multi_data.snapshot_names:
            multi_data.current_snapshot = multi_data.snapshot_names[0]

        return multi_data

    def load_single_snapshot(self, folder_name: str) -> Optional[DashboardData]:
        """단일 스냅샷 로드"""
        folder_path = self.base_path / folder_name
        if folder_path.exists():
            try:
                loader = DataLoader(str(folder_path))
                return loader.load_all()
            except Exception as e:
                print(f"스냅샷 로드 실패: {e}")
        return None


def load_cumulative_data(base_path: str) -> Optional[DashboardData]:
    """모든 스냅샷을 병합하여 누적 데이터 생성"""
    loader = MultiSnapshotLoader(base_path)
    folders = loader.find_snapshot_folders()

    if not folders:
        return None

    all_users = []
    all_conversations = []
    all_messages = []

    for folder in folders:
        try:
            data_loader = DataLoader(str(folder))
            data = data_loader.load_all()

            # 각 데이터프레임에 스냅샷 정보 추가
            users_df = data.users.copy()
            users_df['snapshot'] = folder.name
            all_users.append(users_df)

            convs_df = data.conversations.copy()
            convs_df['snapshot'] = folder.name
            all_conversations.append(convs_df)

            msgs_df = data.messages.copy()
            msgs_df['snapshot'] = folder.name
            all_messages.append(msgs_df)
        except Exception as e:
            print(f"스냅샷 로드 실패 ({folder.name}): {e}")

    if not all_users:
        return None

    # 병합
    merged_users = pd.concat(all_users, ignore_index=True)
    merged_conversations = pd.concat(all_conversations, ignore_index=True)
    merged_messages = pd.concat(all_messages, ignore_index=True)

    # 중복 제거 (uuid 기준으로 최신 스냅샷 데이터 유지)
    merged_users = merged_users.drop_duplicates(subset=['user_uuid'], keep='first')
    merged_conversations = merged_conversations.drop_duplicates(subset=['conv_uuid'], keep='first')
    merged_messages = merged_messages.drop_duplicates(subset=['msg_uuid'], keep='first')

    return DashboardData(
        users=merged_users,
        conversations=merged_conversations,
        messages=merged_messages,
        snapshot_name="전체 누적",
        snapshot_date=None
    )


def load_from_uploaded_files(users_file, conversations_file) -> Optional[DashboardData]:
    """업로드된 파일에서 데이터 로드"""
    try:
        users_data = json.load(users_file)
        users_df = pd.DataFrame(users_data)
        users_df.rename(columns={'uuid': 'user_uuid'}, inplace=True)

        conversations_data = json.load(conversations_file)

        conv_records = []
        msg_records = []

        for conv in conversations_data:
            user_uuid = conv.get('account', {}).get('uuid', '')
            chat_messages = conv.get('chat_messages', [])

            conv_records.append({
                'conv_uuid': conv.get('uuid', ''),
                'name': conv.get('name', '') or '(제목 없음)',
                'summary': conv.get('summary', ''),
                'created_at': pd.to_datetime(conv.get('created_at')),
                'updated_at': pd.to_datetime(conv.get('updated_at')),
                'user_uuid': user_uuid,
                'message_count': len(chat_messages)
            })

            for msg in chat_messages:
                text = msg.get('text', '')
                if not text:
                    content_list = msg.get('content', [])
                    if content_list:
                        texts = [c.get('text', '') for c in content_list if c.get('type') == 'text']
                        text = ' '.join(texts)

                msg_records.append({
                    'msg_uuid': msg.get('uuid', ''),
                    'conv_uuid': conv.get('uuid', ''),
                    'user_uuid': user_uuid,
                    'sender': msg.get('sender', ''),
                    'text': text,
                    'created_at': pd.to_datetime(msg.get('created_at')),
                    'has_attachments': len(msg.get('attachments', [])) > 0,
                    'has_files': len(msg.get('files', [])) > 0
                })

        return DashboardData(
            users=users_df,
            conversations=pd.DataFrame(conv_records),
            messages=pd.DataFrame(msg_records)
        )
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return None
