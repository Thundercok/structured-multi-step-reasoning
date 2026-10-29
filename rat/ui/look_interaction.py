"""Reusable Look interaction state; no Qt, tool execution or model dependency."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingText:
    text: str
    point: object = None


@dataclass
class LookInteraction:
    monitoring: str = 'off'  # off / on / paused
    surface: str = 'hidden'  # hidden / peek / reading
    pending: PendingText | None = None
    pending_notice: str = ''
    pose: str = 'seated'

    def enable(self):
        self.monitoring = 'on'

    def disable(self):
        self.monitoring = 'off'
        self.surface = 'hidden'
        self.clear_pending()

    def pause(self, notice=''):
        self.monitoring = 'paused'
        self.clear_pending()
        self.pending_notice = notice

    def clear_pending(self):
        self.pending = None
        self.pending_notice = ''

    def receive(self, text, point=None):
        if self.monitoring != 'on':
            return
        self.pending = PendingText(text, point) if text else None
        self.pending_notice = '' if text else 'Đoạn quá dài. Bạn chia nhỏ đoạn để mở nhé.'
        # Deliberately no surface transition: copy cannot interrupt reading.

    def peek(self):
        self.surface = 'peek'

    def read(self, pose=None):
        self.surface = 'reading'
        if pose is not None:
            self.pose = pose

    def close(self):
        self.surface = 'hidden'  # Preserve task, pending source and pose.

    def take_pending(self):
        value = self.pending
        if value is not None:
            self.clear_pending()
        return value

    def hint(self, has_result=False, busy=False):
        if self.pending_notice:
            return self.pending_notice
        if self.pending is not None:
            preview = ' '.join(self.pending.text.split())
            if len(preview) > 80:
                preview = preview[:80].rstrip() + '…'
            return 'Chờ dịch: ' + preview
        if busy:
            return 'Đang xử lý yêu cầu trước.'
        if self.monitoring == 'paused':
            return 'Đã tạm dừng Clipboard.'
        if has_result:
            return 'Bấm Chuột để xem lại.'
        if self.monitoring == 'off':
            return 'Viết yêu cầu để bắt đầu.'
        return 'Copy chữ rồi bấm Chuột.'

    def snapshot(self, *, has_result=False, busy=False):
        status = ('Đang xử lý' if busy else 'Có đoạn mới' if self.pending is not None
                  else 'Có thông báo' if self.pending_notice else 'Đang đọc' if self.surface == 'reading' and has_result
                  else 'Clipboard dừng' if self.monitoring == 'paused' else 'Đang chờ' if self.monitoring == 'on' else 'Sẵn sàng')
        return dict(lookStatusLabel=status, lookPendingCount=1 if self.pending is not None else 0,
            lookSurface=self.surface, lookPose=self.pose,
            lookWatching=self.monitoring != 'off', lookPaused=self.monitoring == 'paused',
            lookDismissed=self.surface != 'reading', lookClicked=self.surface == 'reading',
            lookHasQueued=self.pending is not None, lookHasPendingNotice=bool(self.pending_notice),
            lookNotice=self.pending_notice if self.surface == 'peek' else '',
            lookHint=self.hint(has_result, busy))
