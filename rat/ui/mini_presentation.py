"""Mini presentation navigation only; no tool execution, Qt or model calls."""
from dataclasses import dataclass, field
import re


def look_projection(state):
    """Presentation only: short speech uses C; a paragraph uses B.

    The original standing sprite is the whole standby state. Length thresholds
    are layout policy, never intent routing or a model-quality assertion.
    """
    if state.get('busy') or not state.get('hasWorkbench'):
        return dict(lookVariant='standby', lookText='', lookCanCopy=False)
    failed = state.get('phase') in ('error', 'cancelled')
    text = (state.get('status') if failed else
            state.get('agentSummary') or state.get('text') or state.get('status')) or ''
    same_language = (not failed and state.get('view') == 'translation'
                     and not state.get('agentSummary') and bool(state.get('sameLanguageNotice')))
    if same_language:
        text = state['sameLanguageNotice']
    text = text.strip()
    if not text:
        return dict(lookVariant='standby', lookText='', lookCanCopy=False)
    if not failed and (state.get('phase') == 'partial' or state.get('agentIncomplete')):
        text = 'Chưa hoàn tất.\n' + text
    elif (not failed and state.get('view') == 'translation' and state.get('hasOcrSource')
          and state.get('ocrText') != state.get('ocrCommittedText')):
        text = 'Bản dịch trước khi sửa chữ.\n' + text
    sentences = [part for part in re.split(r'[.!?。！？]+\s*', text) if part.strip()]
    short = len(text) <= 100 and len(text.split()) <= 18 and len(sentences) <= 1 and '\n' not in text
    return dict(lookVariant='C' if short else 'B', lookText=text,
                lookCanCopy=not failed and not same_language and bool(state.get('agentSummary') or state.get('text')))


@dataclass
class MiniPresentation:
    surface: str = 'result'
    workspace: str = 'result'
    task_id: int = 0
    scroll: dict = field(default_factory=dict)
    workspace_mode: str = 'single'
    _image_return: str = 'result'
    _settings_return: str = 'result'

    AUXILIARY = frozenset({'welcome', 'help', 'settings'})
    WORKSPACE = frozenset({'result', 'ocr', 'image', 'source'})

    def set_mode(self, mode):
        # Accept the historical name at the boundary; expose Full consistently.
        mode = 'full' if mode == 'multi' else mode
        if mode in ('look', 'minimal', 'single', 'full'):
            self.workspace_mode = mode

    def open(self, surface):
        if surface not in self.AUXILIARY | self.WORKSPACE:
            return
        if surface == 'settings' and self.surface != 'settings':
            self._settings_return = self.surface
        if surface in self.WORKSPACE:
            self.workspace = surface
        self.surface = surface

    def back(self):
        if self.surface == 'settings':
            self.surface = self._settings_return
        elif self.surface in self.AUXILIARY:
            self.surface = self.workspace
        elif self.surface == 'image':
            self.surface = self.workspace = self._image_return
        elif self.surface == 'source':
            self.surface = self.workspace = 'ocr'
        else:
            self.surface = self.workspace = 'result'

    def inspect_image(self):
        self._image_return = self.workspace if self.workspace in ('result', 'ocr', 'source') else 'result'
        self.open('image')

    def begin_task(self):
        self.task_id += 1
        self.scroll.clear()
        self.surface = self.workspace = 'result'

    def complete(self):
        # Observations update the task data, not the user's current reading
        # surface. A completion must not close an image/help view opened while
        # the worker was running. Explicit submissions select result up front.
        if self.surface == 'result':
            self.workspace = 'result'

    @property
    def scroll_key(self):
        return f'{self.task_id}:{self.surface}'

    def snapshot(self):
        return dict(surface=self.surface, taskId=self.task_id,
                    workspaceMode=self.workspace_mode,
                    scrollOffset=self.scroll.get(self.scroll_key, 0.0))
