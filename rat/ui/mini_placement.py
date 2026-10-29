"""Pure layout policy for a fixed-size RAT and its transient workbench."""
from dataclasses import dataclass
from rat.ui.surface_geometry import Rect
from rat.ui.speech_placement import place_speech

# One large Mini character scale. The wide host lets the seated error pose
# reach the same visible height as the standing pose without width-clamping.
RAT_WIDTH, RAT_HEIGHT = 176, 176
LOOK_WIDTH, LOOK_HEIGHT = RAT_WIDTH, RAT_HEIGHT
LOOK_OPTICAL_HEIGHT = 134
MINI_PANEL_WIDTH, MINI_TEXT_SIZE = 580, 16
GAP, MARGIN = 8, 16
FLOAT_HEAD_SIZE, FLOAT_HEAD_OPTICAL = 112, 88


@dataclass(frozen=True)
class Placement:
    panel: Rect
    rat: Rect
    bounds: Rect
    side: str | None


def place_look(available, home, bubble_width=0, bubble_height=0, variant='standby', side=None, *, ink_bounds=None, mouth=None, floating_head=False):
    """Look owns a stable mascot home; shared speech policy places its bubble."""
    width, height = (FLOAT_HEAD_SIZE, FLOAT_HEAD_SIZE) if floating_head else (LOOK_WIDTH, LOOK_HEIGHT)
    # home remains the seated profile's remembered bottom-right anchor. A
    # smaller head shares that anchor, so resizing cannot overwrite its home.
    left = max(available.x+MARGIN, min(round(home[0])+LOOK_WIDTH-width, available.right-MARGIN-width))
    top = max(available.y+MARGIN, min(round(home[1])+LOOK_HEIGHT-height, available.bottom-MARGIN-height))
    rat = Rect(left, top, width, height)
    if bubble_width <= 0 or bubble_height <= 0:
        return Placement(Rect(left, top, 0, 0), rat, rat, side)
    # Shared optical envelope includes the widest seated error pose. The feet
    # baseline is constant; pose-specific ink/mouth still render the tail, but
    # changing expression cannot reposition the speech body.
    ink = (Rect(rat.x+4, rat.y+4, width-8, height-8) if floating_head else
           Rect(rat.x+4, rat.bottom-30-LOOK_OPTICAL_HEIGHT, LOOK_WIDTH-8, LOOK_OPTICAL_HEIGHT))
    anchor_point = (rat.x + mouth[0], rat.y + mouth[1]) if mouth is not None else None
    speech = place_speech(available, ink, bubble_width, bubble_height, preferred_side=side,
                          gap=GAP, margin=MARGIN, anchor_point=anchor_point, align_bottom=True, preserve_side=True)
    return Placement(speech.body, rat, speech.body.union(rat), speech.side)


def place_panel(available, home, height, expanded, side=None, panel_width=580, anchor_top=None, paper_inset=0):
    """home is the user's preferred panel (left, bottom), in screen pixels.

    A narrow screen constrains only the workbench, never the mascot. Dock choice
    remains stable until collapse unless screen space no longer allows it.
    """
    # The production paper has a side gutter above its full-width composer.
    # Dock into that gutter; auxiliary sheets use the external dock (inset 0).
    needed = max(0, RAT_WIDTH + GAP - paper_inset)
    width = min(panel_width, available.width-2*MARGIN-(needed if expanded else 0))
    width = max(1, width)
    height = min(round(height), available.height-2*MARGIN-(0 if expanded else RAT_HEIGHT))
    height = max(1, height)
    left = max(available.x+MARGIN, min(round(home[0]), available.right-MARGIN-width))
    bottom = max(available.y+MARGIN+height+(0 if expanded else RAT_HEIGHT),
                 min(round(home[1]), available.bottom-MARGIN))
    if expanded:
        left_space = left-available.x-MARGIN
        right_space = available.right-MARGIN-left-width
        if side == 'left' and left_space >= needed:
            chosen = 'left'
        elif side == 'right' and right_space >= needed:
            chosen = 'right'
        elif left_space >= needed:
            chosen = 'left'
        elif right_space >= needed:
            chosen = 'right'
        else:
            chosen = side if side in ('left','right') else ('left' if left_space >= right_space else 'right')
            left = (available.x+MARGIN+needed if chosen == 'left'
                    else available.right-MARGIN-width-needed)
        top = bottom-height if anchor_top is None else round(anchor_top)
        top = max(available.y+MARGIN,
                  min(top, available.bottom-MARGIN-max(height, RAT_HEIGHT+12)))
        panel = Rect(left, top, width, height)
        rat_x = panel.x-needed if chosen == 'left' else panel.right+GAP-paper_inset
        rat_y = panel.y+12
    else:
        chosen = None
        panel = Rect(left, bottom-height, width, height)
        rat_x, rat_y = panel.x+6, panel.y-RAT_HEIGHT
    rat = Rect(rat_x, rat_y, RAT_WIDTH, RAT_HEIGHT)
    return Placement(panel, rat, panel.union(rat), chosen)
