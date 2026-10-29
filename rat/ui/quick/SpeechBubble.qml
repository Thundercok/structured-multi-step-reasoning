import QtQuick
import QtQuick.Controls

// Shared presentation: callers supply text/actions/anchor and own execution/lifetime.
SpeechSurface {
    id: bubble
    property string text: ""
    property string stateLabel: ""
    property var actions: [] // {id, label, icon, role: "utility" | "primary", enabled}
    property var taskKey: 0
    property real scrollOffset: 0
    property bool restoringScroll: false
    property real minimumWidth: 76
    property real maximumWidth: 340
    property real maximumHeight: 300
    property real placedWidth: preferredWidth
    property real placedHeight: maximumHeight
    property real fontPixelSize: 13
    // Optional caller-owned input/footer, with no knowledge of its business use.
    property real accessoryHeight: 0
    property alias accessoryHost: accessory
    readonly property var utilityActions: actions.filter(action => action.role !== "primary")
    readonly property var primaryAction: actions.find(action => action.role === "primary") || null
    readonly property real railWidth: utilityActions.length ? 32 : 0
    readonly property real footerHeight: primaryAction ? 30 : 0
    readonly property real headingHeight: stateLabel ? 22 : 0
    readonly property bool hasReader: Boolean(text || stateLabel)
    readonly property real measuredWidth: Math.max(minimumWidth,
        Math.ceil(Math.max(measure.advanceWidth, primaryMeasure.advanceWidth)) + 2 * padding + railWidth + 12)
    readonly property real preferredWidth: heldWidth > 0 ? Math.min(maximumWidth, Math.max(minimumWidth, heldWidth))
        : widthStepFor(measuredWidth, maximumWidth)
    readonly property real naturalHeight: hasReader ? Math.max(
        layoutMeasure.implicitHeight + 2 * padding + headingHeight + footerHeight,
        utilityActions.length * 28 + 4) : Math.max(footerHeight, utilityActions.length * 28)
    readonly property real preferredHeight: Math.min(maximumHeight,
        Math.max(heldHeight, naturalHeight + accessoryHeight))
    readonly property bool overflowing: scroll.contentHeight > scroll.height + 1
    readonly property bool moreBelow: overflowing && scroll.contentY < scroll.contentHeight - scroll.height - 1
    readonly property bool engaged: hover.hovered || scroll.moving || scroll.dragging
        || speech.selectedText.length > 0 || speech.activeFocus || readerMenu.visible
    signal actionTriggered(string actionId, string displayedText)
    signal scrollChanged(real offset)
    signal readingRequested()
    width: Math.max(1, Math.min(preferredWidth, placedWidth))
    height: Math.max(1, Math.min(preferredHeight, placedHeight))
    implicitWidth: preferredWidth
    implicitHeight: preferredHeight
    Accessible.role: Accessible.StaticText
    Accessible.name: stateLabel ? stateLabel + ". " + text : text
    HoverHandler { id: hover }
    TextMetrics { id: measure; text: bubble.text; font: speech.font }
    TextMetrics { id: primaryMeasure; text: bubble.primaryAction ? bubble.primaryAction.label : ""; font.pixelSize: 13 }
    // Measure at the intended tier before resizing the native window. Measuring
    // the old viewport made a short->long response resize once for old wrapping
    // and again for the final width. A screen-clamped viewport can scroll any
    // extra lines; it never needs to expand beyond the common height budget.
    Text {
        id: layoutMeasure
        visible: false; Accessible.ignored: true
        text: bubble.text; textFormat: Text.PlainText
        font: speech.font; wrapMode: Text.Wrap
        width: Math.max(1, bubble.preferredWidth - 2 * bubble.padding - bubble.railWidth - 8)
    }
    // Suppress writes while projecting a different task/status or restoring it.
    property bool rememberPosition: true
    property int savedSelectionStart: 0
    property int savedSelectionEnd: 0
    property string anchorText: ""
    property int anchorPosition: 0
    property real anchorDelta: 0
    readonly property bool menuOpen: readerMenu.visible
    readonly property bool hasSelection: speech.selectedText.length > 0
    signal selectionChanged(int start, int end)
    signal selectionCopyRequested(string selectedText)
    signal readingAnchorChanged(string displayedText, int position, real delta)
    function restoreScroll() {
        if (rememberPosition) {
            scroll.contentY = Math.max(0, Math.min(scrollOffset, Math.max(0, scroll.contentHeight - scroll.height)))
            if (anchorText === text && text.length > 0) {
                var rect = speech.positionToRectangle(Math.min(anchorPosition, speech.length))
                scroll.contentY = Math.max(0, Math.min(rect.y + anchorDelta, Math.max(0, scroll.contentHeight - scroll.height)))
            }
            speech.select(Math.min(savedSelectionStart, speech.length), Math.min(savedSelectionEnd, speech.length))
        } else scroll.contentY = 0
        restoringScroll = false
    }
    function scheduleRestore() { restoringScroll = true; Qt.callLater(restoreScroll) }
    Component.onCompleted: scheduleRestore()
    onTaskKeyChanged: scheduleRestore()
    onTextChanged: scheduleRestore()
    onRememberPositionChanged: scheduleRestore()
    onScrollOffsetChanged: { if (!scroll.moving && !scroll.dragging) scheduleRestore() }
    onVisibleChanged: { if (visible) scheduleRestore() }
    function restoreReading() { scheduleRestore() }
    function focusReader() { speech.forceActiveFocus() }
    Text {
        visible: Boolean(bubble.stateLabel)
        x: bubble.padding; y: bubble.padding
        width: Math.max(1, bubble.width - 2 * bubble.padding - bubble.railWidth)
        height: bubble.headingHeight
        text: bubble.stateLabel; textFormat: Text.PlainText
        color: bubble.inkColor; opacity: 0.65; font.pixelSize: 12
        elide: Text.ElideRight
    }
    Flickable {
        id: scroll
        visible: bubble.hasReader
        objectName: "speechViewport"
        x: bubble.padding; y: bubble.padding + bubble.headingHeight
        width: Math.max(1, bubble.width - 2 * bubble.padding - bubble.railWidth)
        height: Math.max(1, bubble.height - 2 * bubble.padding - bubble.headingHeight - bubble.footerHeight - bubble.accessoryHeight)
        contentWidth: width; contentHeight: speech.contentHeight
        opacity: bubble.restoringScroll ? 0 : 1
        clip: true; boundsBehavior: Flickable.StopAtBounds
        onContentYChanged: {
            if (bubble.visible && bubble.rememberPosition && !bubble.restoringScroll) {
                bubble.scrollChanged(Math.max(0, contentY))
                var position = speech.positionAt(0, Math.max(0, contentY))
                bubble.readingAnchorChanged(speech.text, position, contentY - speech.positionToRectangle(position).y)
            }
        }
        ScrollBar.vertical: ScrollBar {
            objectName: "speechScrollBar"
            policy: bubble.overflowing ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            width: 5
            contentItem: Rectangle { implicitWidth: 3; radius: 1.5; color: bubble.inkColor; opacity: 0.45 }
        }
        TextEdit {
            id: speech
            objectName: "speechText"
            width: Math.max(1, parent.width - 8); text: bubble.text; textFormat: TextEdit.PlainText
            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
            font.pixelSize: bubble.fontPixelSize; color: bubble.inkColor
            selectionColor: bubble.selectionColor
            TapHandler { onTapped: bubble.readingRequested() }
            onSelectedTextChanged: {
                if (bubble.rememberPosition && !bubble.restoringScroll) {
                    bubble.selectionChanged(selectionStart, selectionEnd)
                    if (selectedText.length > 0) bubble.readingRequested()
                }
            }
            Keys.onPressed: event => {
                if (event.matches(StandardKey.Copy) && selectedText.length > 0) {
                    event.accepted = true; bubble.selectionCopyRequested(selectedText)
                }
            }
            MouseArea {
                anchors.fill: parent; acceptedButtons: Qt.RightButton
                onClicked: readerMenu.popup()
            }
        }
    }
    // The final line can be clipped mid-glyph. Keep overflow discoverable even
    // when the pointer is outside and the platform hides transient scroll bars.
    Rectangle {
        objectName: "speechMoreBelow"
        visible: bubble.moreBelow
        x: scroll.x; y: scroll.y + Math.max(0, scroll.height - height)
        width: Math.max(1, scroll.width - 8); height: Math.min(16, scroll.height)
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(bubble.paperColor.r, bubble.paperColor.g, bubble.paperColor.b, 0) }
            GradientStop { position: 1; color: bubble.paperColor }
        }
    }
    Column {
        x: bubble.width - 30; y: 2
        Repeater {
            model: bubble.utilityActions
            delegate: ToolButton {
                required property var modelData
                width: 28; height: 28
                enabled: modelData.enabled !== false
                Accessible.name: modelData.label
                contentItem: DeskIcon { name: modelData.icon || "enter"; color: bubble.inkColor; width: 13; height: 13 }
                background: Rectangle { radius: 6; color: parent.hovered || parent.visualFocus ? bubble.selectionColor : "transparent" }
                onClicked: bubble.actionTriggered(modelData.id, speech.text)
            }
        }
    }
    ToolButton {
        visible: Boolean(bubble.primaryAction)
        x: bubble.padding; y: bubble.height - bubble.footerHeight - bubble.accessoryHeight
        width: Math.max(1, bubble.width - 2 * bubble.padding - bubble.railWidth); height: bubble.footerHeight
        enabled: !bubble.primaryAction || bubble.primaryAction.enabled !== false
        Accessible.name: bubble.primaryAction ? bubble.primaryAction.label : ""
        contentItem: Text { text: bubble.primaryAction ? bubble.primaryAction.label : ""; color: bubble.inkColor; font.pixelSize: 13; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 6; color: parent.hovered || parent.visualFocus ? bubble.selectionColor : "transparent" }
        onClicked: { if (bubble.primaryAction) bubble.actionTriggered(bubble.primaryAction.id, speech.text) }
    }
    Menu {
        id: readerMenu
        popupType: Popup.Window
        MenuItem {
            text: "Sao chép phần đã chọn"; enabled: speech.selectedText.length > 0
            onTriggered: bubble.selectionCopyRequested(speech.selectedText)
        }
        MenuItem { text: "Sao chép nội dung"; onTriggered: bubble.actionTriggered("copy", speech.text) }
    }
    Item {
        id: accessory
        x: 0; y: bubble.height - height
        width: bubble.width; height: bubble.accessoryHeight
    }
}
