"""Pure layout policy for a fixed-size RAT and its transient workbench."""
from dataclasses import dataclass

RAT_WIDTH, RAT_HEIGHT = 122, 128
GAP, MARGIN = 12, 16


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def union(self, other):
        x, y = min(self.x, other.x), min(self.y, other.y)
        return Rect(x, y, max(self.right, other.right)-x, max(self.bottom, other.bottom)-y)


@dataclass(frozen=True)
class Placement:
    panel: Rect
    rat: Rect
    bounds: Rect
    side: str | None


def place_look(available, home, bubble_width=0, bubble_height=0, variant='standby'):
    """Keep one original-sprite anchor; speech never moves the standing home.

    All three poses use the same 122x128 canvas and retain one stable anchor.
    """
    left = max(available.x + MARGIN, min(round(home[0]), available.right - MARGIN - RAT_WIDTH))
    top = max(available.y + MARGIN, min(round(home[1]), available.bottom - MARGIN - RAT_HEIGHT))
    if variant == 'standby':
        rat = Rect(left, top, RAT_WIDTH, RAT_HEIGHT)
        return Placement(Rect(left, top, 0, 0), rat, rat, None)
    rat = Rect(left, top, RAT_WIDTH, RAT_HEIGHT)
    width = max(1, min(round(bubble_width), available.width - 2*MARGIN - rat.width - GAP))
    height = max(1, min(round(bubble_height), available.height - 2*MARGIN))
    left_space = rat.x - available.x - MARGIN
    right_space = available.right - MARGIN - rat.right
    side = 'left' if left_space >= width + GAP or left_space >= right_space else 'right'
    if max(left_space, right_space) < width + GAP:
        width = max(1, max(left_space, right_space) - GAP)
    x = rat.x - GAP - width if side == 'left' else rat.right + GAP
    y = max(available.y + MARGIN, min(rat.y, available.bottom - MARGIN - height))
    panel = Rect(x, y, width, height)
    return Placement(panel, rat, panel.union(rat), side)


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
