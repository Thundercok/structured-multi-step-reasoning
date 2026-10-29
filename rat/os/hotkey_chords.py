"""Supported Carbon chords; the label and native registration share one table."""
CHORDS = {
    'option_shift_r': (15, 2048 | 512, '⌥⇧R'),
    'option_shift_k': (40, 2048 | 512, '⌥⇧K'),
    'option_shift_j': (38, 2048 | 512, '⌥⇧J'),
    'option_shift_space': (49, 2048 | 512, '⌥⇧Space'),
    'control_option_space': (49, 4096 | 2048, '⌃⌥Space'),
    'control_shift_space': (49, 4096 | 512, '⌃⇧Space'),
}
DEFAULT_CHORD = 'option_shift_space'


def chord(value):
    if value not in CHORDS:
        raise ValueError('unsupported_hotkey')
    return CHORDS[value]
