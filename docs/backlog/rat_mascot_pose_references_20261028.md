# RAT mascot pose references — backlog, 2026-10-28

The user supplied these four image sheets as references to save for later use.
They explore standing expressions and gestures, movement, and seated poses.
They are visual reference material, not approved runtime sprites or an instruction
to implement animation or change the current mascot now.

- [Expressions and standing gestures](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_b6k2eyb6k2eyb6k2.png)
- [Standing and resting poses](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_bi7ddmbi7ddmbi7d.png)
- [Movement and expressions](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_403g43403g43403g.png)
- [Seated poses](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_nsb226nsb226nsb2.png)
- [Head expressions](../design/rat-mascot-backlog-20261028/rat-head-expressions.png)

The user has separately specified a rat sitting in a screen corner for Look's
long-content presentation. These sheets may inform a later design, but no
particular pose from them has been selected for that role. Preserve the originals
and revisit selection, asset preparation, and integration when requested.

The user subsequently selected the upper-left head on the head-expressions sheet
for the short-result floating head. A transparent image-generated extraction is
used as `rat/assets/rat_look_head_v2.png` in the Mini source; it is an adaptation,
not a pixel-identical crop. Its appearance in the app remains unverified. The
other expressions remain reference material for later.

## Selected Look idle pose

The user selected this [seated rat reference](../design/rat-mascot-backlog-20261028/rat-look-idle-seated-reference.png)
for Look while waiting for user input. This supersedes the earlier original
standing-only idle decision. A transparent image-generated extraction is wired
as `rat/assets/rat_look_idle_seated_v1.png`, inside the existing 122×128 canvas.
Busy standby keeps the existing standing pose. Other workspaces retain their
mascot. This source change has not been built, launched or tested.

## Error poses and additional sheet

- [Additional gestures sheet](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_1i2ocu1i2ocu1i2o.png): saved for later; no individual pose selected from this new sheet.
- [Skeptical head reference](../design/rat-mascot-backlog-20261028/rat-error-head-reference.png).
- [Shrug reference](../design/rat-mascot-backlog-20261028/rat-shrug-reference.png).
- [Seated error reference](../design/rat-mascot-backlog-20261028/rat-error-seated-reference.png).

User clarification: the seated error rat belongs to Look; the rat sits in Look.
Use `rat_look_error_seated_v1.png` for visible Look errors regardless of message
length and for local input/watcher notices. Do not use the assistant's earlier
proposed short-error-head/clarification-shrug mapping as an approved decision.
The head and shrug remain saved references/adaptations for later use.

The later complete Look source flow supersedes the standing-busy sentence above:
Look uses the seated idle sprite while waiting/working and beside long results,
and the seated error sprite for errors. The previously selected floating head
remains the short successful response projection. All sprites are still in the
fixed 122×128 canvas. No build, test or native UI acceptance for these changes.

## Full RAT character-state sheet — saved for later

User requested “backlog this” for this [six-pose sheet](../design/rat-mascot-backlog-20261028/Gemini_Generated_Image_w68pz4w68pz4w68p.png).
The original PNG is preserved from the user-supplied file
`/Users/thundercock2/Downloads/Gemini_Generated_Image_w68pz4w68pz4w68p.png`.
This reference follows the full RAT reasoning-assistant brief, not a Mini-only
capability description.

Visual inventory, left to right, top row then bottom row: front-facing neutral
stance; leaning forward and inspecting; hand-to-muzzle thinking; small busy-hand
gesture with motion marks; skeptical open-hand gesture; slumped, tired stance.
These descriptions are visual observations, not approved application-state mappings.

Keep this sheet as character/pose reference only. No pose selection, runtime
asset replacement, animation implementation, or change to existing Look behavior
is authorized by this backlog request. The six poses are separate concepts,
not a frame sequence ready for animation.
