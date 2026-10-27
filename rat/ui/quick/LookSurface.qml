import QtQuick
import QtQuick.Controls

// An observation/result projection. No composer, provider or business routing.
Item {
    id: look
    property var snapshot: ({})
    property url mascotSource
    property url headSource
    property url peekSource
    property bool darkMode: false
    property real panelX: 0
    property real panelY: 0
    property real ratX: 0
    property real ratY: 0
    property real maxBubbleHeight: 168
    property real placedBubbleWidth: 320
    property int scrollTask: -1
    readonly property string variant: snapshot.lookVariant || "standby"
    readonly property bool speaking: variant !== "standby" && Boolean(snapshot.lookText)
    readonly property real preferredBubbleWidth: !speaking ? 0 : variant === "C" ? Math.min(220, Math.max(150, measure.advanceWidth + 36)) : 280
    readonly property real bubbleWidth: Math.min(preferredBubbleWidth, placedBubbleWidth > 0 ? placedBubbleWidth : preferredBubbleWidth)
    readonly property real bubbleHeight: !speaking ? 0 : Math.min(maxBubbleHeight, speech.contentHeight + 44)
    readonly property rect bubbleRect: Qt.rect(bubble.x, bubble.y, bubble.width, bubble.height)
    readonly property rect mascotRect: Qt.rect(character.x, character.y, character.width, character.height)
    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    signal moveRequested()
    signal activateRequested()
    signal expandRequested()
    signal menuRequested()
    signal copyRequested(string displayedText)

    function focusSurface() { lookFocus.forceActiveFocus() }
    onSnapshotChanged: {
        if (snapshot.taskId !== scrollTask) {
            scrollTask = snapshot.taskId || 0
            if (speechScroll) speechScroll.contentY = 0
        }
    }
    TextMetrics { id: measure; text: look.snapshot.lookText || ""; font.pixelSize: 13 }
    FocusScope {
        id: lookFocus
        objectName: "lookFocus"
        anchors.fill: parent
        activeFocusOnTab: true
    }
    Rectangle {
        id: bubble
        objectName: "lookSpeechBubble"
        visible: look.speaking
        x: look.panelX; y: look.panelY
        width: look.bubbleWidth; height: look.bubbleHeight
        radius: 14
        color: look.darkMode ? "#2a2c28" : "#fdfdf9"
        border.color: look.darkMode ? "#50564a" : "#dce3d4"
        Accessible.role: Accessible.StaticText
        Accessible.name: look.snapshot.lookText || ""
        Flickable {
            id: speechScroll
            x: 16; y: 12; width: parent.width - 32; height: parent.height - 38
            contentWidth: width; contentHeight: speech.contentHeight
            clip: true; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; active: true; width: 5 }
            TextEdit {
                id: speech
                width: parent.width
                text: look.snapshot.lookText || ""; textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                font.pixelSize: 13; color: look.ink
                selectionColor: look.darkMode ? "#5b6951" : "#dbe7d1"
            }
        }
        Item {
            visible: Boolean(look.snapshot.lookCanCopy)
            x: parent.width - 32; y: parent.height - 28; width: 28; height: 26
            Accessible.role: Accessible.Button; Accessible.name: "Sao chép nội dung đang hiện"
            DeskIcon { anchors.centerIn: parent; width: 14; height: 14; name: "copy"; color: look.ink; opacity: 0.65 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: look.copyRequested(speech.text) }
        }
        Text {
            visible: speechScroll.contentHeight > speechScroll.height + 2 && speechScroll.contentY + speechScroll.height < speechScroll.contentHeight - 2
            x: 16; y: parent.height - 19
            text: "Cuộn để xem tiếp"; font.pixelSize: 10
            color: look.darkMode ? "#b7bdaf" : "#62695e"
        }
    }
    Item {
        id: character
        objectName: "lookMascot"
        x: look.ratX; y: look.ratY
        width: 122; height: 128
        // Generated transparent C/B sprites retain one shared canvas scale;
        // standby remains the original unmodified standing asset.
        Rectangle {
            visible: look.darkMode && look.variant !== "standby"
            x: 24; y: 25; width: 74; height: 66; radius: 33; color: "#eee9e3"
        }
        Image {
            x: 0; y: 0
            width: 122; height: 128
            source: look.variant === "standby" ? look.mascotSource : look.variant === "C" ? look.headSource : look.peekSource
            fillMode: Image.PreserveAspectFit; smooth: true
            Accessible.ignored: true
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
            onPressed: mouse => { look.activateRequested(); pressX = mouse.x; pressY = mouse.y; startedMove = false }
            onPositionChanged: mouse => {
                if (pressed && (pressedButtons & Qt.LeftButton) && !startedMove &&
                        (Math.abs(mouse.x - pressX) > 4 || Math.abs(mouse.y - pressY) > 4)) {
                    startedMove = true; look.moveRequested()
                }
            }
            onClicked: mouse => { if (mouse.button === Qt.RightButton) look.menuRequested() }
            onDoubleClicked: mouse => { if (mouse.button === Qt.LeftButton) look.expandRequested() }
        }
        Accessible.role: Accessible.Button
        Accessible.name: "RAT Look. Thả ảnh để dịch; bấm đúp mở Minimal." + (look.snapshot.lookClicked ? " Đã chọn Chuột." : "")
        Accessible.onPressAction: look.activateRequested()
    }
}
