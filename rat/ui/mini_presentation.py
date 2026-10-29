"""Mini presentation navigation only; no tool execution, Qt or model calls."""
from dataclasses import dataclass, field
import re
from rat.ui.look_interaction import LookInteraction


def compact_speech(text):
    sentences = [part for part in re.split(r'[.!?。！？]+\s*', text) if part.strip()]
    return len(text) <= 100 and len(text.split()) <= 18 and len(sentences) <= 1 and '\n' not in text


def look_projection(state):
    """Presentation only: short speech uses C; a paragraph uses B.

    A seated sprite is the standby/reading indicator. Length thresholds
    are layout policy, never intent routing or a model-quality assertion.
    """
    surface = state.get('lookSurface')
    if surface in ('hidden', 'peek'):
        return dict(lookVariant='standby', lookText=state.get('lookHint', '') if surface == 'peek' else '',
                    lookCanCopy=False, lookShowingError=bool(surface == 'peek' and state.get('lookNotice')))
    pose_variant = 'C' if state.get('lookPose') == 'head' else 'B'
    if surface == 'reading' and state.get('busy'):
        return dict(lookVariant=pose_variant, lookText='Đang xử lý…', lookCanCopy=False, lookShowingError=False)
    if state.get('lookNotice'):
        return dict(lookVariant='C', lookText=state['lookNotice'], lookCanCopy=False)
    if state.get('lookDismissed') or state.get('busy') or not state.get('hasWorkbench'):
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
    return dict(lookVariant=pose_variant if surface == 'reading' else 'C' if compact_speech(text) else 'B', lookText=text,
                lookShowingError=bool(failed),
                lookCanCopy=not failed and not same_language and bool(state.get('agentSummary') or state.get('text')))


@dataclass
class MiniPresentation:
    surface: str = 'result'
    workspace: str = 'result'
    task_id: int = 0
    scroll: dict = field(default_factory=dict)
    selections: dict = field(default_factory=dict)
    extent: str = 'compact'
    composer_visible: bool = True
    source_visible: bool = False
    interaction: LookInteraction = field(default_factory=LookInteraction)
    _image_return: str = 'result'
    _settings_return: str = 'result'

    AUXILIARY = frozenset({'welcome', 'help', 'settings'})
    WORKSPACE = frozenset({'result', 'ocr', 'image', 'source'})

    @property
    def workspace_mode(self):
        """Compatibility projection for old QML/launch callers, never state."""
        if self.extent == 'expanded':
            return 'full' if self.source_visible else 'single'
        return 'minimal' if self.composer_visible else 'look'

    def set_mode(self, mode):
        # Boundary aliases do not enable Clipboard monitoring or replace tasks.
        if mode in ('single', 'full', 'multi'):
            self.extent = 'expanded'
            self.source_visible = mode in ('full', 'multi')
        elif mode in ('look', 'minimal'):
            self.extent = 'compact'
            self.composer_visible = mode == 'minimal'

    def compose(self):
        self.composer_visible = True
        self.interaction.read()

    def read(self):
        self.composer_visible = False
        self.interaction.read()

    def resize(self, expanded):
        self.extent = 'expanded' if expanded else 'compact'

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
        self.selections.clear()
        self.surface = self.workspace = 'result'

    def complete(self):
        # Observations update the task data, not the user's current reading
        # surface. A completion must not close an image/help view opened while
        # the worker was running. Explicit submissions select result up front.
        if self.surface == 'result':
            self.workspace = 'result'

    @property
    def scroll_key(self):
        return f'{self.task_id}:{self.extent}:{self.surface}'

    def snapshot(self):
        return dict(surface=self.surface, taskId=self.task_id,
                    interactionExtent=self.extent, composerVisible=self.composer_visible,
                    sourceVisible=self.source_visible,
                    workspaceMode=self.workspace_mode,
                    scrollOffset=self.scroll.get(self.scroll_key, 0.0))
