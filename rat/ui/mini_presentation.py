"""Mini presentation navigation only; no tool execution, Qt or model calls."""
from dataclasses import dataclass, field


@dataclass
class MiniPresentation:
    surface: str = 'result'
    workspace: str = 'result'
    task_id: int = 0
    _task_sequence: int = 0
    scroll: dict = field(default_factory=dict)
    selections: dict = field(default_factory=dict)
    reading_anchor: tuple = ('', 0, 0.0)
    extent: str = 'compact'
    composer_visible: bool = False
    source_visible: bool = False
    _image_return: str = 'result'
    _settings_return: str = 'result'

    AUXILIARY = frozenset({'welcome', 'help', 'settings'})
    WORKSPACE = frozenset({'result', 'ocr', 'image', 'source'})

    def compose(self):
        self.composer_visible = True

    def read(self):
        self.composer_visible = False

    def resize(self, expanded):
        self.extent = 'expanded' if expanded else 'compact'

    def capture_view(self):
        names = ('surface', 'workspace', 'extent', 'composer_visible', 'source_visible')
        return self.task_id, {name: getattr(self, name) for name in names}

    def restore_view(self, token):
        task_id, fields = token
        if task_id != self.task_id:
            return False
        for name, value in fields.items():
            setattr(self, name, value)
        return True

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
        self._task_sequence = max(self._task_sequence, self.task_id) + 1
        self.task_id = self._task_sequence
        self.scroll.clear()
        self.selections.clear()
        self.reading_anchor = ('', 0, 0.0)
        self.surface = self.workspace = 'result'

    def complete(self):
        if self.surface in ('ocr', 'source', 'image'):
            self.surface = self.workspace = 'result'
        elif self.surface == 'result':
            self.workspace = 'result'

    @property
    def scroll_key(self):
        return f'{self.task_id}:{self.extent}:{self.surface}'

    def snapshot(self):
        return dict(surface=self.surface, taskId=self.task_id,
                    interactionExtent=self.extent, composerVisible=self.composer_visible,
                    sourceVisible=self.source_visible,
                    readerAnchorText=self.reading_anchor[0], readerAnchorPosition=self.reading_anchor[1],
                    readerAnchorDelta=self.reading_anchor[2],
                    lookSelectionStart=self.selections.get(self.task_id, (0, 0))[0],
                    lookSelectionEnd=self.selections.get(self.task_id, (0, 0))[1],
                    scrollOffset=self.scroll.get(self.scroll_key, 0.0))

