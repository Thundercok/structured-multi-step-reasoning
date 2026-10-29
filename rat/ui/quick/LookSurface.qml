import QtQuick
import QtQuick.Controls

// An observation/result projection. No composer, provider or business routing.
Item {
    id: look
    property var snapshot: ({})
    property url mascotSource
    property url idleSource
    property url errorSource
    property url headSource
    property url peekSource
    property real mascotWidth: 176
    property real mascotHeight: 176
    property real seatedOpticalHeight: 134
    property real maximumSpeechWidth: 580
    property real speechFontSize: 16
    property bool darkMode: false
    property real panelX: 0
    property real panelY: 0
    property real ratX: 0
    property real ratY: 0
    property real maxBubbleHeight: 168
    property real placedBubbleWidth: 320
    property real placedBubbleHeight: 300
    property real composerHeight: 0
    property real composerWidthFloor: 380
    property alias composerHost: bubble.accessoryHost
    readonly property string variant: snapshot.lookVariant || "standby"
    readonly property bool reading: snapshot.lookSurface === "reading"
    readonly property bool speaking: Boolean(snapshot.lookText)
    readonly property bool showingError: Boolean(snapshot.lookShowingError)
    readonly property string speechText: snapshot.lookText || ""
    readonly property bool engaged: bubble.engaged || characterMouse.containsMouse || status.hovered
    readonly property bool menuOpen: bubble.menuOpen
    readonly property rect localVisualBounds: pose.visualBounds
    readonly property point localMouth: pose.speechAnchor
    readonly property real preferredBubbleWidth: bubble.preferredWidth
    readonly property real bubbleWidth: bubble.width
    readonly property real bubbleHeight: bubble.height
    readonly property real preferredBubbleHeight: bubble.preferredHeight
    readonly property rect bubbleRect: Qt.rect(bubble.x + bubble.occupiedRect.x, bubble.y + bubble.occupiedRect.y,
        bubble.occupiedRect.width, bubble.occupiedRect.height)
    readonly property rect mascotRect: Qt.rect(character.x, character.y, character.width, character.height)
    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    signal moveRequested()
    signal activateRequested()
    signal expandRequested()
    signal menuRequested(real x, real y)
    signal settingsRequested()
    signal workbenchRequested()
    signal selectionRequested(int start, int end)
    signal selectionCopyRequested(string text)
    signal copyRequested(string displayedText)
    signal dismissRequested()
    signal retryRequested()
    signal scrollRequested(real offset)
    signal pendingRequested()
    signal previewRequested()
    signal openRequested()
    signal recallRequested()

    function focusSurface() { bubble.focusReader() }
    function restoreReading() { bubble.restoreReading() }
    function prepareSnapshot(next) {
        // Capture the old rendered geometry BEFORE busy text/actions replace
        // the result. Completion releases it for one coalesced placement pass.
        if (next.busy && !snapshot.busy && next.lookSurface === "reading") {
            if (speaking && bubble.width > 0 && bubble.height > 0)
                bubble.holdSize(bubble.width, bubble.height)
            else bubble.holdSize(bubble.widthStepFor(300, maximumSpeechWidth), 96)
        }
    }
    function beginPresentation() { bubble.releaseSize() }
    onReadingChanged: { if (reading) bubble.restoreReading() }
    FocusScope {
        id: lookFocus
        objectName: "lookFocus"
        anchors.fill: parent
        activeFocusOnTab: true
    }
    SpeechBubble {
        id: bubble
        objectName: "lookSpeechBubble"
        x: look.panelX; y: look.panelY
        text: look.speechText
        accessoryHeight: look.composerHeight
        minimumWidth: look.snapshot.composerVisible ? look.composerWidthFloor : 76
        maximumWidth: look.maximumSpeechWidth
        fontPixelSize: look.speechFontSize
        cornerRadius: 18
        padding: 14
        maximumHeight: look.maxBubbleHeight
        placedWidth: look.placedBubbleWidth
        placedHeight: look.placedBubbleHeight
        anchorPoint: Qt.point(character.x + pose.speechAnchor.x - x, character.y + pose.speechAnchor.y - y)
        paperColor: look.darkMode ? "#2b3227" : "#fdfefb"
        edgeColor: look.darkMode ? "#424d39" : "#e0e5d8"
        inkColor: look.ink
        selectionColor: look.darkMode ? "#5b6951" : "#dbe7d1"
        taskKey: look.reading ? "task:" + look.snapshot.taskId : "peek"
        rememberPosition: look.reading && !look.snapshot.busy && !look.showingError
        scrollOffset: look.snapshot.lookScrollOffset || 0
        savedSelectionStart: look.snapshot.lookSelectionStart || 0
        savedSelectionEnd: look.snapshot.lookSelectionEnd || 0
        actions: {
            var items = [{id:"dismiss", label:"Đóng phản hồi", icon:"close", role:"utility"}]
            if (look.reading && look.snapshot.lookCanCopy)
                items.push({id:"copy", label:"Sao chép nội dung đang hiện", icon:"copy", role:"utility"})
            if (look.reading && look.snapshot.hasWorkbench)
                items.push({id:"workbench", label:"Mở rộng", icon:"chevron-up", role:"utility"})
            if (look.reading && !look.snapshot.composerVisible)
                items.push({id:"reply", label:"Viết yêu cầu", icon:"enter", role:"utility"})
            if (look.reading && look.showingError && (look.snapshot.translationSettingsSuggested || look.snapshot.finderSettingsSuggested))
                items.push({id:"settings", label:"Mở cài đặt", role:"primary"})
            else if (look.reading && look.showingError && look.snapshot.canRetryRequest)
                items.push({id:"retry", label:"Thử lại", role:"primary"})
            else if (look.reading && look.snapshot.phase === "needs_input" && !look.snapshot.composerVisible)
                items.push({id:"reply", label:"Trả lời…", role:"primary"})
            else if (!look.reading && look.snapshot.lookHasQueued)
                items.push({id:"next", label:"Dịch đoạn này", role:"primary", enabled:!look.snapshot.busy})
            else if (!look.reading && look.snapshot.hasWorkbench)
                items.push({id:"recall", label:"Xem lại kết quả", role:"primary"})
            return items
        }
        onScrollChanged: offset => { if (look.reading) look.scrollRequested(offset) }
        onSelectionChanged: (start, end) => look.selectionRequested(start, end)
        onSelectionCopyRequested: text => look.selectionCopyRequested(text)
        onReadingRequested: look.activateRequested()
        onActionTriggered: (actionId, displayedText) => {
            if (actionId === "copy") look.copyRequested(displayedText)
            else if (actionId === "dismiss") look.dismissRequested()
            else if (actionId === "retry") look.retryRequested()
            else if (actionId === "reply") look.expandRequested()
            else if (actionId === "next") look.pendingRequested()
            else if (actionId === "recall") look.recallRequested()
            else if (actionId === "settings") look.settingsRequested()
            else if (actionId === "workbench") look.workbenchRequested()
        }
    }
    Item {
        id: character
        objectName: "lookMascot"
        x: look.ratX; y: look.ratY
        width: look.mascotWidth; height: look.mascotHeight
        MascotPose {
            id: pose
            objectName: "lookOpticalPose"
            anchors.fill: parent
            bottomPadding: 30
            // Keep one silhouette and scale throughout Look. Response length
            // changes the reading surface, never the character's identity.
            source: look.showingError ? look.errorSource : look.idleSource
            // Metadata is normalized to each source canvas, not window size.
            inkBounds: look.showingError ? Qt.rect(0.04, 0.06, 0.92, 0.87) : Qt.rect(0.08, 0.06, 0.86, 0.88)
            mouth: look.showingError ? Qt.point(0.43, 0.40) : Qt.point(0.44, 0.43)
            opticalHeight: look.seatedOpticalHeight
        }
        CompanionStatus {
            id: status; z: 2; objectName: "lookStatus"
            x: (character.width - width) / 2
            y: character.height - height
            label: look.snapshot.lookHasQueued ? "đoạn chờ" : look.snapshot.lookStatusLabel || "Đang chờ"
            pending: Boolean(look.snapshot.lookHasQueued)
            busy: Boolean(look.snapshot.busy); paused: Boolean(look.snapshot.lookPaused)
            paperColor: bubble.paperColor; inkColor: bubble.inkColor; edgeColor: bubble.edgeColor
            onClicked: { if (look.snapshot.lookHasQueued) look.previewRequested(); else look.openRequested() }
        }
        Rectangle {
            visible: Boolean(look.snapshot.dropActive)
            anchors.fill: parent; radius: 12; color: "transparent"
            border.color: look.darkMode ? "#c0d2a7" : "#4f6740"; border.width: 2
        }
        MouseArea {
            id: characterMouse
            objectName: "lookCharacterMouse"
            property real pressX: 0
            property real pressY: 0
            property bool startedMove: false
            anchors.fill: parent; hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: Qt.OpenHandCursor
            onPressed: mouse => { pressX = mouse.x; pressY = mouse.y; startedMove = false }
            onPositionChanged: mouse => {
                if (pressed && (pressedButtons & Qt.LeftButton) && !startedMove &&
                        (Math.abs(mouse.x - pressX) > 4 || Math.abs(mouse.y - pressY) > 4)) {
                    startedMove = true; look.moveRequested()
                }
            }
            onClicked: mouse => {
                if (mouse.button === Qt.RightButton) { look.activateRequested(); look.menuRequested(character.x + mouse.x, character.y + mouse.y) }
                else if (!startedMove) look.openRequested()
            }
        }
        Accessible.role: Accessible.Button
        Accessible.name: "RAT Lite. Bấm để xem lại công việc; kéo để di chuyển."
        Accessible.onPressAction: look.openRequested()
    }
}
