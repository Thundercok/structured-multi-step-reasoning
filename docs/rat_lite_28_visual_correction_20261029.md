# .28 source correction — character first, compact speech

User feedback on the live .27: the mouse was much too small. “Compact” meant
an unobtrusive speech bubble next to a recognizable character, like the supplied
Safari reference, rather than shrinking the character to a tiny icon. The user
also explicitly removed the visible Copy button from the requested design.

The correction keeps the existing head artwork and increases its host from
44 to 112 logical px, with optical target 88 rather than 30. The optical renderer
still constrains to the host aspect ratio; these are source dimensions, not a
measurement from the running app. Native placement and QML now receive sizes
from one shared policy so the pointer mask and artwork cannot diverge.

A completed compact translation/analysis shows the result and a small Close
control. It has no title/status stack, Copy CTA, provider/language row or details
button. The bubble fits short content instead of retaining the working-state
reader height; long output still scrolls. Details are available from the head's
menu and the expanded view. Errors, partial output and dirty-source warnings
remain visible. Copy via text selection and the reader context menu remains.
Visible Copy CTAs were removed from both complete and partial output.

Idle ordinary recall presents the character; click it to toggle the existing
composer. Explicit “Viết yêu cầu” and --minimal still request typing. No business
tools, source contracts, model opt-in or acceptance/research gates change.

Status: source only. No build, launch, test, screenshot tour or model execution
performed for this correction. The running .27 has not been replaced. The source
identity advances to .28 so a later requested build is distinguishable.
