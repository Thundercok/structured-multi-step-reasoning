import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: desk
    objectName: "paperDesk"
    width: 640
    height: 640
    color: darkMode ? "#181c16" : "#f4f6f0"

    property bool darkMode: false
    property bool reduceMotion: false
    property url mascotSource
    property string previewScene: "idle"
    property string phase: "idle"
    property bool expanded: false
    property bool unread: false
    property bool sourceOpen: false
    property bool logOpen: false
    property bool compactTrail: false
    property bool copied: false
    property bool readyForMotion: false
    property var liveController: null
    property var liveSnapshot: ({})
    readonly property bool liveMode: liveController !== null
    readonly property bool hasWorkbench: liveMode ? Boolean(liveSnapshot.hasWorkbench) : phase === "working" || phase === "result"
    readonly property bool noticeVisible: liveMode ? unread && !expanded : phase === "result" && unread && !expanded
    readonly property string sceneKey: hasWorkbench ? (expanded ? phase : unread ? "unread" : "folded") : phase
    readonly property bool animationsRunning: composerResize.running || paperMove.running
    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color backingColor: darkMode ? "#3a4332" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color onAccent: darkMode ? "#24301b" : "#fafcf5"

    signal copyRequested(string text)

    function syncLive() {
        if (!liveMode) return
        const next = liveController.snapshot
        if (next.pageNumber !== liveSnapshot.pageNumber || next.view !== "page") copied = false
        liveSnapshot = next
        phase = next.phase
        expanded = next.expanded
        unread = next.unread
    }

    function applyScene(scene) {
        if (liveMode) return
        phase = scene === "unread" || scene === "folded" ? "result" : scene
        expanded = scene === "working" || scene === "result"
        unread = scene === "unread"
        sourceOpen = false
        logOpen = false
        copied = false
    }
    function openWorkbench() {
        if (!hasWorkbench) return
        if (liveMode) { liveController.setExpanded(true); return }
        expanded = true
        unread = false
    }
    function foldWorkbench() {
        if (liveMode) { liveController.setExpanded(false); editor.forceActiveFocus(); return }
        expanded = false
        unread = false
        editor.forceActiveFocus()
    }
    function submitDraft() {
        if (liveMode) { if (!liveSnapshot.busy) liveController.search(editor.text); return }
        if (phase === "receiving" || editor.text.trim().length === 0) return
        phase = "receiving"
        expanded = false
        unread = false
        sourceOpen = false
        logOpen = false
    }
    function stopRequest() {
        if (liveMode) { liveController.cancel(); editor.forceActiveFocus(); return }
        if (phase === "receiving") {
            phase = "idle"
            expanded = false
            editor.forceActiveFocus()
        }
    }
    function requestCopy() {
        if (liveMode) {
            if (liveController.copyCitation(pageText.selectedText)) { copied = true; copyFeedback.restart() }
            return
        }
        copyRequested("Tối đa 24 tín chỉ cho học kỳ chính. Học kỳ hè tối đa 12 tín chỉ.\n(Nội dung minh họa.)")
        copied = true
        copyFeedback.restart()
    }
    onPreviewSceneChanged: applyScene(previewScene)
    Component.onCompleted: { if (liveMode) syncLive(); else applyScene(previewScene); readyForMotion = true }

    Connections {
        target: desk.liveController
        function onChanged() { desk.syncLive() }
    }
    FileDialog {
        id: pdfDialog
        title: "Chọn một PDF để tìm và đọc"
        nameFilters: ["PDF (*.pdf *.PDF)"]
        onAccepted: { if (desk.liveMode) desk.liveController.selectFile(String(selectedFile)) }
    }
    DropArea {
        anchors.fill: parent
        enabled: desk.liveMode
        onDropped: drop => {
            if (drop.hasUrls && drop.urls.length === 1) {
                desk.liveController.selectFile(String(drop.urls[0]))
                drop.accepted = true
            } else drop.accepted = false
        }
    }

    Timer {
        id: copyFeedback
        interval: 1600
        repeat: false
        onTriggered: desk.copied = false
    }

    component QuietButton: Button {
        id: control
        property bool primary: false
        font.pixelSize: 12
        leftPadding: 9
        rightPadding: 9
        topPadding: 7
        bottomPadding: 7
        contentItem: Text {
            text: control.text
            color: control.primary ? desk.onAccent : desk.muted
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
        }
        background: Rectangle {
            radius: 8
            color: control.primary ? desk.accent : control.hovered ? desk.backingColor : "transparent"
            border.color: desk.accent
            border.width: control.visualFocus ? 2 : 0
        }
    }

    ColumnLayout {
        x: 32
        y: 20
        width: parent.width - 64
        spacing: 6
        RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Label { text: desk.liveMode ? "RAT · PDF offline" : "RAT · Qt Quick · Nội dung minh họa"; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: desk.liveMode }
        QuietButton { objectName: "choosePdf"; visible: desk.liveMode; text: "Chọn PDF"; onClicked: pdfDialog.open() }
        QuietButton { objectName: "openOriginal"; visible: desk.liveMode && Boolean(desk.liveSnapshot.fileName); text: "Mở PDF gốc"; onClicked: desk.liveController.openOriginal() }
        ComboBox {
            id: scenePicker
            objectName: "scenePicker"
            textRole: "label"
            valueRole: "scene"
            implicitWidth: 205
            Accessible.name: "Trạng thái minh họa"
            visible: !desk.liveMode
            currentIndex: ["idle", "unread", "folded", "startup", "receiving", "working", "result"].indexOf(desk.sceneKey)
            model: [
                {label: "Mặc định · Simple", scene: "idle"},
                {label: "Simple · Có !", scene: "unread"},
                {label: "Simple · Đã xem", scene: "folded"},
                {label: "Khởi động RAT", scene: "startup"},
                {label: "Đang nhận yêu cầu", scene: "receiving"},
                {label: "Workbench · Đang làm", scene: "working"},
                {label: "Workbench · Kết quả", scene: "result"}
            ]
            onActivated: desk.previewScene = currentValue
        }
        }
        RowLayout {
            visible: desk.liveMode && Boolean(desk.liveSnapshot.fileName)
            Layout.fillWidth: true
            spacing: 8
            Label {
                Layout.fillWidth: true
                text: desk.liveSnapshot.fileName + " · " + desk.liveSnapshot.pageCount + " trang"
                textFormat: Text.PlainText
                elide: Text.ElideMiddle
                color: desk.muted
                font.pixelSize: 12
            }
            SpinBox { id: pagePicker; objectName: "pagePicker"; from: 1; to: desk.liveSnapshot.pageCount || 1; editable: true; implicitWidth: 95; Accessible.name: "Số trang PDF từ 1" }
            QuietButton { objectName: "readPage"; text: "Đọc trang"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.readPage(pagePicker.value) }
        }
    }

    Item {
        id: unit
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 32
        anchors.rightMargin: 32
        anchors.bottomMargin: 28
        height: parent.height - 100
        readonly property int paperOffset: width < 520 ? 110 : 128

        Rectangle {
            visible: desk.expanded && desk.hasWorkbench
            x: resultPaper.x - 8
            y: resultPaper.y - 5
            width: resultPaper.width
            height: resultPaper.height
            radius: 15
            rotation: -0.9
            color: desk.backingColor
        }
        Rectangle {
            id: resultPaper
            objectName: "resultPaper"
            visible: desk.expanded && desk.hasWorkbench
            x: unit.paperOffset
            y: composer.y + 22 - height
            width: unit.width - x
            height: Math.min(resultContents.implicitHeight + (desk.liveMode ? 80 : 38), composer.y + 22 - (desk.liveMode ? 110 : 70))
            radius: 16
            color: desk.paperColor
            border.color: desk.edge
            Behavior on y {
                enabled: desk.readyForMotion && !desk.reduceMotion
                NumberAnimation { id: paperMove; duration: 160; easing.type: Easing.OutCubic }
            }
            RowLayout {
                visible: desk.liveMode
                x: 18
                y: 10
                width: parent.width - 36
                spacing: 5
                QuietButton { objectName: "backToSearch"; visible: Boolean(desk.liveSnapshot.canBack); text: "← Kết quả tìm"; onClicked: desk.liveController.backToSearch() }
                Item { Layout.fillWidth: true }
                QuietButton { objectName: "copyCitation"; visible: Boolean(desk.liveSnapshot.canCopy); text: desk.copied ? "Đã chép" : "Chép trích dẫn"; onClicked: desk.requestCopy() }
                QuietButton { objectName: "liveFoldButton"; text: "−"; Accessible.name: "Thu workbench"; onClicked: desk.foldWorkbench() }
            }
            ScrollView {
                id: resultScroll
                x: 22
                y: desk.liveMode ? 58 : 16
                width: parent.width - 44
                height: parent.height - (desk.liveMode ? 80 : 38)
                contentWidth: availableWidth
                contentHeight: resultContents.implicitHeight
                clip: true
            ColumnLayout {
                id: resultContents
                width: resultScroll.availableWidth
                spacing: 13
                RowLayout {
                    visible: !desk.liveMode
                    Layout.fillWidth: true
                    Label {
                        Layout.fillWidth: true
                        text: desk.liveMode ? (desk.liveSnapshot.query || desk.liveSnapshot.fileName || "PDF") : "Tối đa bao nhiêu tín chỉ mỗi học kỳ?"
                        textFormat: Text.PlainText
                        color: desk.muted
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                    QuietButton { objectName: "foldButton"; text: "−"; Accessible.name: "Thu workbench"; onClicked: desk.foldWorkbench() }
                }
                Label {
                    Layout.fillWidth: true
                    text: desk.liveMode ? (desk.liveSnapshot.title || "Đang mở bàn làm việc…") : desk.phase === "working" ? "Mình đang đối chiếu quy chế." : "Tối đa 24 tín chỉ cho học kỳ chính."
                    textFormat: Text.PlainText
                    color: desk.ink
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    wrapMode: Text.Wrap
                }
                Label {
                    visible: !desk.liveMode && desk.phase === "result"
                    Layout.fillWidth: true
                    text: "Với học kỳ hè, giới hạn là 12 tín chỉ."
                    color: desk.ink
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
                Label {
                    visible: !desk.liveMode && desk.phase === "result"
                    Layout.fillWidth: true
                    text: "Nhớ kiểm tra điều kiện tiên quyết và lịch học trước khi đăng ký."
                    color: desk.muted
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
                RowLayout {
                    visible: !desk.liveMode && desk.phase === "working"
                    Layout.fillWidth: true
                    Label { text: "Luồng thao tác minh họa"; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    QuietButton {
                        objectName: "trailMode"
                        text: desk.compactTrail ? "Xem trực quan" : "Xem gọn"
                        onClicked: desk.compactTrail = !desk.compactTrail
                    }
                }
                ColumnLayout {
                    visible: !desk.liveMode && desk.phase === "working" && !desk.compactTrail
                    Layout.fillWidth: true
                    spacing: 11
                    Repeater {
                        model: ["✓  Đọc yêu cầu", "✓  Đọc tài liệu được chọn", "●  Đối chiếu điều kiện", "○  Soạn câu trả lời"]
                        Label { required property string modelData; text: modelData; color: desk.ink; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    }
                }
                Label {
                    visible: !desk.liveMode && desk.phase === "working" && desk.compactTrail
                    text: "●  Đối chiếu điều kiện · 3 / 4"
                    color: desk.ink
                    font.pixelSize: 13
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                Label {
                    visible: !desk.liveMode && desk.sourceOpen
                    text: "Quy chế học vụ · bản mẫu\nHọc kỳ chính tối đa 24 tín chỉ; học kỳ hè tối đa 12 tín chỉ."
                    color: desk.muted
                    font.pixelSize: 13
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                Label {
                    visible: !desk.liveMode && desk.logOpen && desk.phase === "result"
                    text: "Đã nhận yêu cầu → Đọc đoạn tài liệu → Đối chiếu hai học kỳ → Tạo câu trả lời."
                    color: desk.muted
                    font.pixelSize: 13
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                ColumnLayout {
                    visible: desk.liveMode
                    Layout.fillWidth: true
                    spacing: 12
                    Label {
                        Layout.fillWidth: true
                        text: (desk.liveSnapshot.view === "error" ? desk.liveSnapshot.errorText : desk.liveSnapshot.status) || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: desk.muted
                        font.pixelSize: 13
                    }
                    Loader {
                        Layout.fillWidth: true
                        active: desk.liveMode && desk.liveSnapshot.busy
                        visible: active
                        sourceComponent: ProgressBar { indeterminate: true; palette.highlight: desk.accent; Accessible.name: "Đang đọc PDF" }
                    }
                    Repeater {
                        model: desk.liveSnapshot.items || []
                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 7
                            Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: "Trang PDF " + modelData.page + " · " + modelData.page_label; textFormat: Text.PlainText; color: desk.accent; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                QuietButton { objectName: "readHit_" + modelData.page; text: "Đọc trang"; onClicked: desk.liveController.readPage(modelData.page) }
                            }
                            Label { text: modelData.snippet; textFormat: Text.PlainText; color: desk.ink; font.pixelSize: 13; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                    }
                    TextArea {
                        id: pageText
                        objectName: "pageText"
                        visible: desk.liveSnapshot.view === "page"
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight
                        text: desk.liveSnapshot.pageText || ""
                        textFormat: TextEdit.PlainText
                        wrapMode: TextEdit.Wrap
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        color: desk.ink
                        selectionColor: desk.accent
                        selectedTextColor: desk.onAccent
                        font.pixelSize: 14
                        padding: 0
                        background: null
                        Accessible.name: "Văn bản trích xuất từ trang PDF đang đọc"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QuietButton { objectName: "nextBatch"; visible: desk.liveSnapshot.nextPage > 0; text: "Tìm tiếp từ trang " + desk.liveSnapshot.nextPage; onClicked: desk.liveController.nextBatch() }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                    RowLayout {
                        Layout.fillWidth: true
                        QuietButton { text: "Nhật ký"; onClicked: desk.logOpen = !desk.logOpen }
                        Item { Layout.fillWidth: true }
                    }
                    Repeater {
                        model: desk.logOpen ? (desk.liveSnapshot.events || []) : []
                        Label { required property string modelData; text: "· " + modelData; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true }
                    }
                }
                Rectangle { visible: !desk.liveMode; Layout.fillWidth: true; height: 1; color: desk.edge }
                RowLayout {
                    visible: !desk.liveMode
                    Layout.fillWidth: true
                    spacing: 4
                    QuietButton { text: "1 nguồn"; Accessible.name: "Mở nguồn minh họa"; onClicked: desk.sourceOpen = !desk.sourceOpen }
                    QuietButton {
                        text: desk.phase === "working" ? "3 / 4 bước" : "4 bước"
                        Accessible.name: "Luồng thao tác công khai"
                        onClicked: { if (desk.phase === "working") desk.compactTrail = !desk.compactTrail; else desk.logOpen = !desk.logOpen }
                    }
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: desk.phase === "result"; text: desk.copied ? "Đã chép" : "Sao chép"; onClicked: desk.requestCopy() }
                }
            }
            }
        }

        Rectangle {
            x: composer.x + 12
            y: composer.y - 4
            width: unit.width - 20
            height: composer.height - 5
            radius: 11
            rotation: -0.8
            color: desk.backingColor
            z: 2
        }
        Button {
            id: note
            objectName: "notice"
            visible: !desk.expanded && desk.hasWorkbench
            x: 126
            y: composer.y - (desk.noticeVisible ? 54 : 41)
            width: Math.min(228, unit.width - x - 20)
            height: desk.noticeVisible ? 61 : 48
            rotation: -1.2
            z: 3
            Accessible.name: desk.noticeVisible ? "Có kết quả mới, mở workbench" : "Mở lại workbench"
            onClicked: desk.openWorkbench()
            background: Rectangle {
                radius: 12
                color: note.hovered ? desk.backingColor : desk.paperColor
                border.width: note.visualFocus ? 2 : 1
                border.color: note.visualFocus ? desk.accent : desk.edge
            }
            contentItem: RowLayout {
                spacing: 9
                Rectangle {
                    visible: desk.noticeVisible
                    width: 25
                    height: 25
                    radius: 13
                    color: desk.accent
                    Label { anchors.centerIn: parent; text: "!"; color: desk.onAccent; font.pixelSize: 18; font.weight: Font.Medium }
                }
                Label { Layout.fillWidth: true; text: desk.liveMode && desk.liveSnapshot.errorCode ? "Xem thông báo" : desk.phase === "working" ? "Xem tiến trình" : "Xem kết quả"; color: desk.accent; font.pixelSize: 13; wrapMode: Text.Wrap }
                Label { text: "⌃"; color: desk.accent; font.pixelSize: 15 }
            }
            bottomPadding: 17
            leftPadding: 16
            rightPadding: 16
        }
        Item {
            objectName: "mascotCrop"
            x: 4
            y: composer.y - 116
            width: 122
            height: 116
            clip: true
            z: 4
            Image {
                width: 180
                height: width * (sourceSize.height / Math.max(1, sourceSize.width))
                source: desk.mascotSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                Accessible.ignored: true
            }
        }
        Rectangle {
            id: composer
            objectName: "composer"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            height: desk.phase === "startup" ? 94 : Math.max(94, editorColumn.implicitHeight + 26)
            radius: 17
            color: desk.inputColor
            border.color: editor.activeFocus ? desk.accent : desk.edge
            z: 5
            Behavior on height {
                enabled: desk.readyForMotion && !desk.reduceMotion
                NumberAnimation { id: composerResize; duration: 160; easing.type: Easing.OutCubic }
            }
            ColumnLayout {
                visible: desk.phase === "startup"
                anchors.fill: parent
                anchors.margins: 15
                spacing: 15
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "RAT"; color: desk.accent; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true }
                    Label { text: "Đang mở bàn làm việc…"; color: desk.muted; font.pixelSize: 13 }
                }
                Loader {
                    Layout.fillWidth: true
                    active: desk.phase === "startup"
                    sourceComponent: ProgressBar { indeterminate: true; palette.highlight: desk.accent; Accessible.name: "Đang chuẩn bị giao diện" }
                }
            }
            ColumnLayout {
                id: editorColumn
                visible: desk.phase !== "startup"
                x: 14
                y: 13
                width: parent.width - 28
                spacing: 7
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    TextArea {
                        id: editor
                        objectName: "draftEditor"
                        Accessible.name: "Nhập yêu cầu"
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: Math.max(30, contentHeight + 4)
                        padding: 0
                        topPadding: 4
                        font.pixelSize: 15
                        color: desk.ink
                        placeholderTextColor: desk.muted
                        placeholderText: desk.liveMode ? (desk.liveSnapshot.fileName ? "Tìm từ hoặc cụm từ trong PDF…" : "Chọn hoặc thả một PDF để bắt đầu…") : desk.phase === "idle" ? "Chuột nghe đây. Bạn cần gì?" : "Hỏi tiếp hoặc sửa điều gì đó…"
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        background: null
                        Keys.onReturnPressed: event => {
                            if (!(event.modifiers & Qt.ShiftModifier) && !inputMethodComposing) { event.accepted = true; desk.submitDraft() }
                            else event.accepted = false
                        }
                        Keys.onEnterPressed: event => {
                            if (!(event.modifiers & Qt.ShiftModifier) && !inputMethodComposing) { event.accepted = true; desk.submitDraft() }
                            else event.accepted = false
                        }
                    }
                    QuietButton {
                        objectName: "sendButton"
                        text: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy) ? "■" : "↑"
                        Accessible.name: desk.liveMode ? (desk.liveSnapshot.busy ? "Dừng đọc PDF" : "Tìm trong PDF") : desk.phase === "receiving" ? "Dừng yêu cầu minh họa" : "Gửi yêu cầu minh họa"
                        primary: true
                        implicitWidth: 34
                        implicitHeight: 34
                        Layout.alignment: Qt.AlignTop
                        font.pixelSize: 18
                        onClicked: { if (desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy)) desk.stopRequest(); else desk.submitDraft() }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Label { visible: desk.phase === "idle" && !desk.liveMode; text: "↵ Gửi · ⇧↵ Xuống dòng"; color: desk.muted; font.pixelSize: 11 }
                    Label {
                        visible: desk.liveMode
                        text: (desk.liveSnapshot.busy ? desk.liveSnapshot.status : (desk.liveSnapshot.fileName ? desk.liveSnapshot.fileName : desk.liveSnapshot.status)) || ""
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        color: desk.muted
                        font.pixelSize: 11
                    }
                    Label { visible: desk.phase === "receiving"; text: "Đang nhận yêu cầu…"; color: desk.muted; font.pixelSize: 12 }
                    QuietButton {
                        visible: !desk.liveMode && desk.hasWorkbench
                        text: "Quy chế học vụ"
                        onClicked: { desk.openWorkbench(); desk.sourceOpen = true }
                    }
                    Item { Layout.fillWidth: true }
                }
                Loader {
                    Layout.fillWidth: true
                    active: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy)
                    visible: active
                    sourceComponent: ProgressBar { indeterminate: true; palette.highlight: desk.accent; Accessible.name: "Đang nhận yêu cầu" }
                }
            }
        }
    }
    Shortcut {
        sequence: "Ctrl+L"
        enabled: desk.hasWorkbench
        onActivated: { if (desk.expanded) desk.foldWorkbench(); else desk.openWorkbench() }
    }
    Shortcut {
        sequence: "Meta+L"
        enabled: desk.hasWorkbench
        onActivated: { if (desk.expanded) desk.foldWorkbench(); else desk.openWorkbench() }
    }
}
