import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: desk
    objectName: "paperDesk"
    width: 640
    height: 640
    color: floatingWindow ? "transparent" : (darkMode ? "#181c16" : "#f4f6f0")

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
    property bool answerSourcesOpen: false
    property bool answerQuestionOpen: false
    property bool copied: false
    property bool readyForMotion: false
    property var liveController: null
    property var liveSnapshot: ({})
    property int selectedFinderIndex: -1
    property int selectedAppGridIndex: 0
    readonly property bool liveMode: liveController !== null
    // Keep rich text stable when only mode/status changes; reparsing loses selection.
    readonly property string displayedAnswerHtml: (darkMode ? liveSnapshot.answerHtmlDark : liveSnapshot.answerHtml) || ""
    readonly property int gridColumns: Math.max(3, Math.min(6, Math.floor(resultScroll.availableWidth / 105)))
    readonly property var allApps: desk.liveSnapshot.installedApps || []
    readonly property var filteredApps: {
        var q = (editor.text || "").trim().toLowerCase()
        if (!q || desk.liveSnapshot.view !== "apps") return desk.allApps
        return desk.allApps.filter(function(app) {
            if (app.name && app.name.toLowerCase().indexOf(q) !== -1) return true
            if (app.bundle_id && app.bundle_id.toLowerCase().indexOf(q) !== -1) return true
            if (app.names && app.names.some(function(alias) { return alias.toLowerCase().indexOf(q) !== -1 })) return true
            return false
        })
    }

    onSelectedFinderIndexChanged: {
        if (selectedFinderIndex >= 0 && liveSnapshot.view === "finder") {
            var item = finderRepeater.itemAt(selectedFinderIndex)
            if (item && resultScroll.contentHeight > resultScroll.height) {
                var itemTop = item.y
                var itemBottom = item.y + item.height
                var viewTop = resultScroll.ScrollBar.vertical.position * resultScroll.contentHeight
                var viewBottom = viewTop + resultScroll.height
                if (itemTop < viewTop) {
                    resultScroll.ScrollBar.vertical.position = Math.max(0, itemTop / resultScroll.contentHeight)
                } else if (itemBottom > viewBottom) {
                    resultScroll.ScrollBar.vertical.position = Math.min(1, (itemBottom - resultScroll.height) / resultScroll.contentHeight)
                }
            }
        }
    }

    function scrollAppIntoView(idx) {
        if (!appsResultsLoader.item) return
        var repeater = appsResultsLoader.item.appsRepeaterItem
        if (!repeater) return
        var cell = repeater.itemAt(idx)
        if (!cell) return
        if (resultScroll.contentHeight <= resultScroll.height) return

        var point = cell.mapToItem(resultContents, 0, 0)
        var itemTop = point.y
        var itemBottom = point.y + cell.height + 46

        var viewTop = resultScroll.ScrollBar.vertical.position * resultScroll.contentHeight
        var viewBottom = viewTop + resultScroll.height

        if (itemTop < viewTop) {
            resultScroll.ScrollBar.vertical.position = Math.max(0, itemTop / resultScroll.contentHeight)
        } else if (itemBottom > viewBottom) {
            resultScroll.ScrollBar.vertical.position = Math.min(
                1.0 - (resultScroll.height / resultScroll.contentHeight),
                (itemBottom - resultScroll.height) / resultScroll.contentHeight
            )
        }
    }

    onSelectedAppGridIndexChanged: {
        if (selectedAppGridIndex >= 0 && liveSnapshot.view === "apps") {
            scrollAppIntoView(selectedAppGridIndex)
        }
    }

    onFilteredAppsChanged: {
        if (desk.liveSnapshot.view === "apps") {
            if (desk.filteredApps.length === 0) {
                desk.selectedAppGridIndex = -1
            } else if (desk.selectedAppGridIndex < 0 || desk.selectedAppGridIndex >= desk.filteredApps.length) {
                desk.selectedAppGridIndex = 0
            }
        }
    }
    property bool floatingWindow: liveMode
    property real maxPaperHeight: 420
    readonly property real preferredWindowHeight: 48 + composer.height + Math.max(116, expanded && hasWorkbench ? resultPaper.height - 22 : 0)
    readonly property bool hasWorkbench: liveMode ? Boolean(liveSnapshot.hasWorkbench) : phase === "working" || phase === "result"
    readonly property bool hasAnswerPreview: liveMode && liveSnapshot.view === "answer"
    readonly property bool incompletePreview: hasAnswerPreview && liveSnapshot.answerOutcome !== "completed"
    readonly property string previewBody: liveSnapshot.answerExcerpt || (incompletePreview ? (liveSnapshot.status || "Yêu cầu chưa hoàn tất") : "Mở câu trả lời đầy đủ")
    readonly property string previewMeta: incompletePreview ? (liveSnapshot.answerOutcome === "cancelled" ? "Đã dừng · chưa hoàn tất" : "Chưa hoàn tất · mở để xem thông báo")
        : "Xem nhanh" + ((liveSnapshot.answerSources || []).length ? " · " + liveSnapshot.answerSources.length + " tham chiếu" : "")
          + " · " + (liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra được báo cáo" : liveSnapshot.answerVerification === "FAIL" ? "Kiểm tra chưa đạt" : "Chưa xác minh")
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
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color warningInk: darkMode ? "#e4bb89" : "#916329"
    readonly property color pdfInk: darkMode ? "#dbaa9f" : "#a15e50"
    // Shared states for the live desk; retain the existing paper/sage palette.
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
    readonly property int cardRadius: 10
    readonly property int controlRadius: 8

    signal copyRequested(string text)
    signal moveRequested()
    signal closeRequested()

    function syncLive() {
        if (!liveMode) return
        const next = liveController.snapshot
        if (next.pageNumber !== liveSnapshot.pageNumber || next.fileName !== liveSnapshot.fileName || next.view !== "page") copied = false
        if (next.fileName !== liveSnapshot.fileName) pagePicker.value = 1
        if (next.view === "page" && next.pageNumber) pagePicker.value = next.pageNumber
        if (next.view !== "finder") selectedFinderIndex = -1
        else if (selectedFinderIndex >= (next.finderHits || []).length) selectedFinderIndex = -1
        if (next.view !== "apps") selectedAppGridIndex = 0
        if (next.answerText !== liveSnapshot.answerText || next.userQuery !== liveSnapshot.userQuery) {
            answerSourcesOpen = false
            answerQuestionOpen = false
        }
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
        if (liveMode) {
            if (!liveSnapshot.busy) {
                const pdfSearch = Boolean(liveSnapshot.fileName)
                liveController.search(editor.text)
                if (!pdfSearch && liveController.snapshot.busy) editor.text = ""
            }
            return
        }
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
            var sel = desk.liveSnapshot.view === "answer" ? answerText.selectedText : pageText.selectedText;
            if (liveController.copyCitation(sel)) { copied = true; copyFeedback.restart() }
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

    component DeskProgress: ProgressBar {
        id: progress
        implicitHeight: 3
        background: Rectangle { radius: 2; color: desk.edge }
        contentItem: Item {
            clip: true
            Rectangle {
                id: progressSegment
                width: Math.max(24, parent.width * 0.24)
                height: parent.height
                radius: 2
                color: desk.accent
                NumberAnimation on x {
                    from: -progressSegment.width
                    to: progress.width
                    duration: 1350
                    loops: Animation.Infinite
                    running: progress.visible && !desk.reduceMotion
                }
            }
        }
    }

    component QuietButton: Button {
        id: control
        property bool primary: false
        property bool elideText: false
        opacity: enabled ? 1 : 0.45
        hoverEnabled: true
        font.pixelSize: 12
        leftPadding: 9
        rightPadding: 9
        topPadding: 7
        bottomPadding: 7
        property string iconName: ""
        property string trailingIconName: ""
        property int iconSize: 16
        contentItem: RowLayout {
            property color color: control.primary ? desk.accentText : control.highlighted ? desk.accent : desk.muted
            spacing: control.iconName && control.text ? 6 : 0
            DeskIcon {
                visible: Boolean(control.iconName)
                name: control.iconName
                color: parent.color
                Layout.preferredWidth: control.iconSize
                Layout.preferredHeight: control.iconSize
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                visible: Boolean(control.text)
                Layout.fillWidth: true
                text: control.text
                color: parent.color
                font: control.font
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                wrapMode: control.elideText ? Text.NoWrap : Text.Wrap
                elide: control.elideText ? Text.ElideMiddle : Text.ElideNone
            }
            DeskIcon {
                visible: Boolean(control.trailingIconName)
                name: control.trailingIconName
                color: parent.color
                Layout.preferredWidth: 12
                Layout.preferredHeight: 12
                Layout.alignment: Qt.AlignVCenter
            }
        }
        background: Rectangle {
            radius: desk.controlRadius
            color: control.primary
                ? (control.down ? Qt.darker(desk.accent, 1.12) : control.hovered ? Qt.darker(desk.accent, 1.05) : desk.accent)
                : (control.down || control.highlighted ? desk.selectedSurface : control.hovered ? desk.hoverSurface : "transparent")
            border.color: desk.accent
            border.width: control.visualFocus ? 2 : 0
        }
    }

    // A quiet action button, with its keyboard shortcut as supporting text.
    component KeycapBadge: Button {
        id: keycapRoot
        property string keyText: ""
        property string labelText: ""
        property bool primary: false
        text: labelText
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: labelText + ", " + keyText
        implicitWidth: implicitContentWidth + leftPadding + rightPadding
        implicitHeight: 26
        leftPadding: 6
        rightPadding: 6
        topPadding: 3
        bottomPadding: 3
        Layout.alignment: Qt.AlignVCenter
        opacity: enabled ? 1 : 0.45

        contentItem: RowLayout {
            spacing: 5
            Label {
                text: keycapRoot.labelText
                color: keycapRoot.primary ? desk.accent : desk.muted
                font.pixelSize: 11
                font.weight: keycapRoot.primary ? Font.Medium : Font.Normal
            }
            Label {
                text: keycapRoot.keyText
                color: desk.muted
                font.pixelSize: 10
            }
        }
        background: Rectangle {
            radius: 6
            color: keycapRoot.down ? desk.backingColor
                : keycapRoot.primary ? desk.selectedSurface
                : keycapRoot.hovered ? desk.hoverSurface : "transparent"
            border.color: desk.accent
            border.width: keycapRoot.visualFocus ? 2 : 0
        }
    }

    component IconButton: Button {
        id: iconControl
        property string glyph: "eye"
        property int iconSize: 16
        opacity: enabled ? 1 : 0.45
        hoverEnabled: true
        implicitWidth: 28
        implicitHeight: 28
        padding: 6
        contentItem: Item {
            implicitWidth: iconControl.iconSize
            implicitHeight: iconControl.iconSize
            DeskIcon {
                anchors.centerIn: parent
                name: iconControl.glyph
                color: desk.muted
                width: iconControl.iconSize
                height: iconControl.iconSize
            }
        }
        background: Rectangle {
            radius: 6
            color: iconControl.down ? desk.selectedSurface : iconControl.hovered ? desk.hoverSurface : "transparent"
            border.color: desk.accent
            border.width: iconControl.visualFocus ? 1 : 0
        }
    }

    ColumnLayout {
        visible: !desk.liveMode
        x: 32
        y: 20
        width: parent.width - 64
        spacing: 6
        RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Label { text: desk.liveMode ? "RAT · PDF offline" : "RAT · Qt Quick · Nội dung minh họa"; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: desk.liveMode }
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
    }

    Item {
        id: unit
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: desk.liveMode ? 24 : 32
        anchors.rightMargin: desk.liveMode ? 24 : 32
        anchors.bottomMargin: desk.liveMode ? 24 : 28
        height: parent.height - (desk.liveMode ? 48 : 100)
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
            width: composer.width - x
            height: desk.liveMode ? Math.min(resultContents.implicitHeight + 80, desk.maxPaperHeight) : Math.min(resultContents.implicitHeight + 38, composer.y + 22 - 70)
            radius: 16
            color: desk.paperColor
            border.color: desk.edge
            Behavior on y {
                enabled: desk.readyForMotion && !desk.reduceMotion
                NumberAnimation { id: paperMove; duration: 160; easing.type: Easing.OutCubic }
            }
            RowLayout {
                visible: desk.liveMode
                x: 22
                y: 10
                width: parent.width - 44
                spacing: 5
                Label {
                    visible: !desk.liveSnapshot.canBack && desk.liveSnapshot.view !== "apps"
                    text: desk.liveSnapshot.view === "page" ? "Đang đọc"
                        : (desk.liveSnapshot.view === "answer" ? "Câu trả lời"
                        : (desk.liveSnapshot.view === "busy" ? "Đang xử lý"
                        : (desk.liveSnapshot.view === "finder" ? "Tìm kiếm" : "Trong tài liệu"))
                        )
                    font.pixelSize: desk.liveSnapshot.view === "answer" ? 18 : 11
                    font.weight: desk.liveSnapshot.view === "answer" ? Font.Medium : Font.Normal
                    color: desk.liveSnapshot.view === "answer" ? desk.ink : desk.muted
                }
                QuietButton { objectName: "backToSearch"; visible: Boolean(desk.liveSnapshot.canBack); text: "← Kết quả tìm"; onClicked: desk.liveController.backToSearch() }
                QuietButton {
                    objectName: "backFromApps"
                    visible: desk.liveSnapshot.view === "apps"
                    text: "← Bàn làm việc"
                    onClicked: {
                        var restored = desk.liveController.closeAppsView()
                        if (restored) editor.text = restored
                        editor.forceActiveFocus()
                    }
                }
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.OpenHandCursor
                        onPressed: desk.moveRequested()
                    }
                }
                QuietButton { objectName: "copyCitation"; visible: Boolean(desk.liveSnapshot.canCopy); text: desk.copied ? "Đã chép" : (desk.liveSnapshot.view === "answer" ? "Sao chép" : "Chép trích dẫn"); iconName: desk.copied ? "check" : "copy"; onClicked: desk.requestCopy() }
                QuietButton { objectName: "liveFoldButton"; text: ""; iconName: "minus"; Accessible.name: "Thu workbench"; onClicked: desk.foldWorkbench() }
            }
            ScrollView {
                id: resultScroll
                objectName: "resultScroll"
                x: 22
                y: desk.liveMode ? 48 : 16
                width: parent.width - 44
                height: Math.max(0, parent.height - (desk.liveMode ? 80 : 38))
                contentWidth: availableWidth
                contentHeight: resultContents.implicitHeight
                clip: true
            ColumnLayout {
                id: resultContents
                width: resultScroll.availableWidth
                spacing: 10
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
                    QuietButton { objectName: "foldButton"; text: ""; iconName: "minus"; Accessible.name: "Thu workbench"; onClicked: desk.foldWorkbench() }
                }
                Label {
                    visible: !desk.liveMode || desk.liveSnapshot.view !== "answer"
                    Layout.fillWidth: true
                    text: desk.liveMode ? (
                        desk.liveSnapshot.view === "page" ? "Trang " + desk.liveSnapshot.pageNumber
                        : (desk.liveSnapshot.view === "answer" ? (desk.liveSnapshot.userQuery || "")
                        : (desk.liveSnapshot.view === "finder" ? (desk.liveSnapshot.title || "Tìm kiếm")
                        : (desk.liveSnapshot.view === "apps" ? ("Ứng dụng (" + desk.filteredApps.length + ")")
                        : (desk.liveSnapshot.title || "Đang mở bàn làm việc…"))))
                    ) : desk.phase === "working" ? "Mình đang đối chiếu quy chế." : "Tối đa 24 tín chỉ cho học kỳ chính."
                    textFormat: Text.PlainText
                    color: desk.ink
                    font.pixelSize: desk.liveMode ? 16 : 20
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
                    ColumnLayout {
                        visible: desk.liveSnapshot.view === "answer"
                        Layout.fillWidth: true
                        spacing: 4
                        Button {
                            id: answerQuestion
                            objectName: "answerQuestion"
                            Layout.fillWidth: true
                            padding: 0
                            hoverEnabled: true
                            Accessible.name: "Câu hỏi: " + (desk.liveSnapshot.userQuery || "")
                            Accessible.description: "Mở hoặc thu câu hỏi đầy đủ"
                            onClicked: desk.answerQuestionOpen = !desk.answerQuestionOpen
                            contentItem: Text {
                                text: desk.liveSnapshot.userQuery || ""
                                textFormat: Text.PlainText
                                font.pixelSize: 12
                                color: desk.muted
                                wrapMode: desk.answerQuestionOpen ? Text.Wrap : Text.NoWrap
                                elide: desk.answerQuestionOpen ? Text.ElideNone : Text.ElideRight
                            }
                            background: Rectangle { color: "transparent"; radius: 3; border.color: desk.accent; border.width: answerQuestion.visualFocus ? 1 : 0 }
                            ToolTip.visible: hovered
                            ToolTip.text: desk.liveSnapshot.userQuery || ""
                        }
                        Label {
                            id: answerStatus
                            objectName: "answerStatus"
                            visible: Boolean(text)
                            Layout.fillWidth: true
                            text: desk.liveSnapshot.status || ""
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: desk.muted
                            font.pixelSize: 11
                        }
                        Item { Layout.preferredHeight: 2 }
                    }
                    TextArea {
                        id: answerText
                        objectName: "answerText"
                        visible: desk.liveSnapshot.view === "answer"
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight
                        text: desk.displayedAnswerHtml
                        textFormat: TextEdit.RichText
                        wrapMode: TextEdit.Wrap
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        color: desk.ink
                        selectionColor: desk.accent
                        selectedTextColor: desk.accentText
                        font.pixelSize: 14
                        padding: 0
                        background: null
                        Accessible.name: "Câu trả lời của trợ lý"
                    }
                    ColumnLayout {
                        id: answerReferences
                        objectName: "answerReferences"
                        visible: desk.liveSnapshot.view === "answer"
                        Layout.fillWidth: true
                        spacing: 8
                        Item { Layout.preferredHeight: 4 }
                        Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            QuietButton {
                                objectName: "answerSourcesToggle"
                                visible: (desk.liveSnapshot.answerSources || []).length > 0
                                text: (desk.liveSnapshot.answerSources || []).length + " tham chiếu"
                                iconName: desk.answerSourcesOpen ? "chevron-down" : "chevron-right"
                                leftPadding: 0
                                topPadding: 4
                                bottomPadding: 4
                                Accessible.name: (desk.answerSourcesOpen ? "Thu" : "Mở") + " tham chiếu của lượt trả lời"
                                Accessible.role: Accessible.Button
                                checkable: true
                                checked: desk.answerSourcesOpen
                                onClicked: desk.answerSourcesOpen = !desk.answerSourcesOpen
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                objectName: "answerVerification"
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignRight
                                text: desk.liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra được báo cáo"
                                    : desk.liveSnapshot.answerVerification === "FAIL" ? "Kiểm tra chưa đạt" : "Chưa được xác minh"
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                                font.pixelSize: 11
                                wrapMode: Text.Wrap
                            }
                        }
                        ColumnLayout {
                            visible: desk.answerSourcesOpen
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: desk.liveSnapshot.view === "answer" ? (desk.liveSnapshot.answerSources || []) : []
                                RowLayout {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    spacing: 8
                                    DeskIcon { name: "file"; color: desk.muted; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                                    Label {
                                        text: modelData.title + (modelData.page > 0 ? "" : " · " + modelData.location)
                                        textFormat: Text.PlainText
                                        font.pixelSize: 12
                                        color: desk.muted
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                    QuietButton {
                                        objectName: "openAnswerSource_" + index
                                        visible: modelData.page > 0
                                        enabled: modelData.canOpen
                                        text: "Trang " + modelData.page
                                        Accessible.name: "Đọc trang " + modelData.page + ", " + modelData.title
                                        topPadding: 4
                                        bottomPadding: 4
                                        onClicked: desk.liveController.openAnswerSource(index)
                                    }
                                }
                            }
                        }
                    }
                    Label {
                        visible: desk.liveSnapshot.view !== "answer" && desk.liveSnapshot.view !== "busy" && desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "apps"
                        Layout.fillWidth: true
                        text: desk.liveSnapshot.view === "page" ? (desk.liveSnapshot.fileName + " · nhãn " + desk.liveSnapshot.pageLabel + (desk.liveSnapshot.pageTruncated ? " · Đã cắt ở 8.000 ký tự" : "") + "\nBôi chọn đoạn cần lấy, rồi chép trích dẫn.") : (desk.liveSnapshot.view === "error" ? desk.liveSnapshot.errorText : desk.liveSnapshot.status) || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: desk.muted
                        font.pixelSize: 13
                    }
                    Loader {
                        Layout.fillWidth: true
                        active: desk.liveMode && desk.liveSnapshot.busy
                        visible: active
                        sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang xử lý yêu cầu" }
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
                        selectedTextColor: desk.accentText
                        font.pixelSize: 14
                        padding: 0
                        background: null
                        Accessible.name: "Văn bản trích xuất từ trang PDF đang đọc"
                    }
                    ColumnLayout {
                        id: finderResults
                        objectName: "finderResults"
                        visible: desk.liveSnapshot.view === "finder" && (desk.liveSnapshot.finderHits || []).length > 0
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            id: finderRepeater
                            model: desk.liveSnapshot.finderHits || []
                            ColumnLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 4

                                // Section header when category changes
                                Label {
                                    visible: Boolean(modelData.is_first_of_section)
                                        && (desk.liveSnapshot.finderHits || []).some(function(hit) { return hit.kind !== modelData.kind })
                                    text: modelData.kind === "application" ? "Ứng dụng" : "Tài liệu & tệp"
                                    color: desk.muted
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    Layout.topMargin: index === 0 ? 0 : 8
                                    Layout.bottomMargin: 2
                                }

                                Rectangle {
                                    id: hitCard
                                    objectName: "finderHit_" + index
                                    Layout.fillWidth: true
                                    implicitHeight: hitRow.implicitHeight + 14
                                    radius: desk.cardRadius
                                    readonly property bool isSelected: desk.selectedFinderIndex === index
                                    color: hitCard.isSelected ? desk.selectedSurface : "transparent"
                                    border.color: hitCard.isSelected ? desk.selectedEdge : "transparent"
                                    border.width: 1

                                    MouseArea {
                                        anchors.fill: parent
                                        z: 0
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onEntered: desk.selectedFinderIndex = index
                                        onClicked: {
                                            desk.selectedFinderIndex = index
                                            editor.forceActiveFocus()
                                        }
                                        onDoubleClicked: {
                                            desk.liveController.openSelectedHit(index)
                                        }
                                    }

                                    RowLayout {
                                        id: hitRow
                                        z: 1
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        anchors.leftMargin: 10
                                        spacing: 10

                                        Item {
                                            Layout.preferredWidth: 28
                                            Layout.preferredHeight: 32
                                            Layout.alignment: Qt.AlignTop
                                            Image {
                                                anchors.centerIn: parent
                                                visible: modelData.kind === "application"
                                                width: 28; height: 28
                                                source: visible && modelData.path ? "image://icon/" + modelData.path : ""
                                                sourceSize.width: 56; sourceSize.height: 56
                                                fillMode: Image.PreserveAspectFit
                                                smooth: true
                                            }
                                            DeskIcon {
                                                anchors.centerIn: parent
                                                visible: modelData.kind !== "application"
                                                name: modelData.is_pdf ? "pdf" : "file"
                                                color: modelData.is_pdf ? desk.pdfInk : desk.muted
                                                width: 22; height: 22
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: 3
                                            Label {
                                                objectName: "finderTitle_" + index
                                                text: modelData.title
                                                textFormat: Text.PlainText
                                                color: desk.ink
                                                font.pixelSize: 13
                                                font.weight: Font.Medium
                                                elide: Text.ElideRight
                                                maximumLineCount: 2
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 6
                                                Label {
                                                    text: (modelData.parent_name || (modelData.kind === "application" ? "Ứng dụng" : modelData.is_pdf ? "PDF" : "Tệp"))
                                                        + " · " + (modelData.snippet || modelData.display_path || modelData.path || "")
                                                    textFormat: Text.PlainText
                                                    color: desk.muted
                                                    font.pixelSize: 11
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                    Layout.minimumWidth: 0
                                                }
                                                // Reserve the action slots so selection never shifts text.
                                                RowLayout {
                                                    visible: Boolean(modelData.path)
                                                    opacity: hitCard.isSelected ? 1 : 0
                                                    enabled: hitCard.isSelected
                                                    spacing: 2
                                                    IconButton {
                                                        glyph: "eye"
                                                        Accessible.name: "Xem nhanh QuickLook"
                                                        onClicked: desk.liveController.previewHit(modelData.path)
                                                    }
                                                    IconButton {
                                                        glyph: "folder"
                                                        Accessible.name: "Hiện trong Finder"
                                                        onClicked: desk.liveController.revealInFinder(modelData.path)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Bottom Action Bar reflecting selected hit actions cleanly with tactile keycaps
                        Rectangle {
                            id: bottomActionBar
                            objectName: "bottomActionBar"
                            visible: desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.liveSnapshot.finderHits || []).length
                            Layout.fillWidth: true
                            implicitHeight: finderShortcuts.implicitHeight + 12
                            radius: desk.controlRadius
                            color: "transparent"

                            readonly property var selectedHit: (desk.liveSnapshot.finderHits || [])[desk.selectedFinderIndex] || ({})

                            Flow {
                                id: finderShortcuts
                                x: 0
                                y: 6
                                width: parent.width
                                spacing: 10

                                KeycapBadge {
                                    objectName: "finderReadAction"
                                    visible: Boolean(bottomActionBar.selectedHit.is_pdf)
                                    keyText: "↵"
                                    labelText: bottomActionBar.width < 400 ? "Đọc" : "Đọc trực tiếp"
                                    Accessible.name: "Đọc PDF đã chọn, Enter"
                                    primary: true
                                    onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex)
                                }
                                KeycapBadge {
                                    visible: Boolean(bottomActionBar.selectedHit.is_pdf)
                                    keyText: "⇧↵"
                                    labelText: bottomActionBar.width < 400 ? "Hỏi" : "Hỏi về PDF"
                                    Accessible.name: "Hỏi về PDF đã chọn, Shift Enter"
                                    onClicked: {
                                        desk.liveController.selectFile(bottomActionBar.selectedHit.path)
                                        editor.forceActiveFocus()
                                    }
                                }
                                KeycapBadge {
                                    visible: bottomActionBar.selectedHit.kind === "application"
                                    keyText: "↵"
                                    labelText: bottomActionBar.width < 400 ? "Mở" : "Mở ứng dụng"
                                    primary: true
                                    onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex)
                                }
                                KeycapBadge {
                                    visible: bottomActionBar.selectedHit.kind === "file" && !bottomActionBar.selectedHit.is_pdf
                                    keyText: "↵"
                                    labelText: bottomActionBar.width < 400 ? "Mở" : "Mở tệp"
                                    onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex)
                                }
                                KeycapBadge {
                                    visible: bottomActionBar.selectedHit.kind === "file" && !bottomActionBar.selectedHit.is_pdf
                                    keyText: "⇧↵"
                                    labelText: bottomActionBar.width < 400 ? "Hỏi" : "Hỏi về tệp"
                                    primary: true
                                    onClicked: desk.liveController.askAboutSelectedHit(desk.selectedFinderIndex, editor.text)
                                }
                                KeycapBadge {
                                    visible: Boolean(bottomActionBar.selectedHit.path)
                                    keyText: "⌘Y"
                                    labelText: "Xem nhanh"
                                    onClicked: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
                                }
                                KeycapBadge {
                                    visible: Boolean(bottomActionBar.selectedHit.path)
                                    keyText: "⌘↵"
                                    labelText: "Finder"
                                    onClicked: desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex)
                                }
                            }
                        }
                    }

                    // APPS CATALOG GRID VIEW (loaded lazily on demand)
                    Loader {
                        id: appsResultsLoader
                        objectName: "appsResultsLoader"
                        active: desk.liveMode && desk.liveSnapshot.view === "apps"
                        visible: active
                        Layout.fillWidth: true
                        sourceComponent: Component {
                            ColumnLayout {
                                id: appsResults
                                objectName: "appsResults"
                                property alias appsRepeaterItem: appsRepeater
                                Layout.fillWidth: true
                                spacing: 12

                                // State 3: Empty State (when filter matches no app)
                                Rectangle {
                                    id: appsEmptyCard
                                    objectName: "appsEmptyCard"
                                    visible: desk.filteredApps.length === 0
                                    Layout.fillWidth: true
                                    implicitHeight: emptyColumn.implicitHeight + 32
                                    radius: desk.cardRadius
                                    color: desk.utilitySurface
                                    border.color: desk.edge

                                    ColumnLayout {
                                        id: emptyColumn
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.margins: 16
                                        spacing: 8

                                        DeskIcon {
                                            name: "search"
                                            color: desk.muted
                                            Layout.alignment: Qt.AlignHCenter
                                            Layout.preferredWidth: 28
                                            Layout.preferredHeight: 28
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignHCenter
                                            text: "Không tìm thấy ứng dụng khớp với \"" + (editor.text || "").trim() + "\""
                                            color: desk.ink
                                            font.pixelSize: 13
                                            font.weight: Font.Medium
                                            horizontalAlignment: Text.AlignHCenter
                                            wrapMode: Text.Wrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignHCenter
                                            text: "Thử tìm theo tên tiếng Anh, alias hoặc xóa bộ lọc."
                                            color: desk.muted
                                            font.pixelSize: 11
                                            horizontalAlignment: Text.AlignHCenter
                                            wrapMode: Text.Wrap
                                        }

                                        RowLayout {
                                            Layout.alignment: Qt.AlignHCenter
                                            spacing: 10
                                            Layout.topMargin: 4

                                            QuietButton {
                                                objectName: "clearAppsFilter"
                                                text: "Xóa bộ lọc"
                                                primary: true
                                                onClicked: {
                                                    editor.text = ""
                                                    editor.forceActiveFocus()
                                                }
                                            }
                                            QuietButton {
                                                objectName: "exitAppsView"
                                                text: "Về Bàn làm việc"
                                                onClicked: {
                                                    var restored = desk.liveController.closeAppsView()
                                                    if (restored) editor.text = restored
                                                    editor.forceActiveFocus()
                                                }
                                            }
                                        }
                                    }
                                }

                                // State 1 & State 2: Grid View (Unfiltered & Filtered)
                                Flow {
                                    id: appsGridFlow
                                    objectName: "appsGridFlow"
                                    visible: desk.filteredApps.length > 0
                                    Layout.fillWidth: true
                                    spacing: 10

                                    readonly property int cardWidth: Math.max(90, Math.floor((resultScroll.availableWidth - 10 * (desk.gridColumns - 1)) / desk.gridColumns))

                                    Repeater {
                                        id: appsRepeater
                                        model: desk.filteredApps

                                        Rectangle {
                                            id: appCell
                                            objectName: "appCard_" + index
                                            width: appsGridFlow.cardWidth
                                            height: 112
                                            radius: desk.cardRadius
                                            readonly property bool isSelected: desk.selectedAppGridIndex === index
                                            readonly property bool isHovered: cellMouse.containsMouse
                                            color: isSelected
                                                ? desk.selectedSurface
                                                : (isHovered
                                                    ? desk.hoverSurface
                                                    : (desk.darkMode ? Qt.rgba(1, 1, 1, 0.03) : Qt.rgba(0, 0, 0, 0.02)))
                                            border.color: isSelected
                                                ? desk.selectedEdge
                                                : "transparent"
                                            border.width: 1

                                            MouseArea {
                                                id: cellMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onEntered: desk.selectedAppGridIndex = index
                                                onClicked: {
                                                    desk.liveController.launchApplication(modelData.path)
                                                    var restored = desk.liveController.closeAppsView()
                                                    if (restored) editor.text = restored
                                                }
                                            }

                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 6
                                                anchors.topMargin: 8
                                                anchors.bottomMargin: 6
                                                spacing: 5

                                                Image {
                                                    Layout.alignment: Qt.AlignHCenter
                                                    Layout.preferredWidth: 52
                                                    Layout.preferredHeight: 52
                                                    Layout.minimumWidth: 52
                                                    Layout.minimumHeight: 52
                                                    Layout.maximumWidth: 52
                                                    Layout.maximumHeight: 52
                                                    width: 52
                                                    height: 52
                                                    source: modelData.icon_url || ("image://icon/" + modelData.path)
                                                    sourceSize.width: 104
                                                    sourceSize.height: 104
                                                    fillMode: Image.PreserveAspectFit
                                                    smooth: true
                                                    mipmap: true
                                                }

                                                Label {
                                                    Layout.fillWidth: true
                                                    Layout.fillHeight: true
                                                    Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
                                                    text: modelData.name || ""
                                                    color: desk.ink
                                                    font.pixelSize: 12
                                                    font.weight: Font.Normal
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignTop
                                                    elide: Text.ElideRight
                                                    maximumLineCount: 2
                                                    wrapMode: Text.Wrap
                                                    lineHeight: 1.15
                                                }
                                            }
                                        }
                                    }
                                }

                                // Bottom Action Bar for selected app in grid
                                Rectangle {
                                    id: appsBottomBar
                                    objectName: "appsBottomBar"
                                    visible: desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length
                                    Layout.fillWidth: true
                                    implicitHeight: appShortcuts.implicitHeight + 12
                                    radius: desk.controlRadius
                                    color: "transparent"

                                    readonly property var currentApp: desk.filteredApps[desk.selectedAppGridIndex] || ({})

                                    Flow {
                                        id: appShortcuts
                                        x: 0
                                        y: 6
                                        width: parent.width
                                        spacing: appsBottomBar.width < 400 ? 6 : 8

                                        Label {
                                            id: bottomBarAppName
                                            text: appsBottomBar.currentApp.name || ""
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                            color: desk.ink
                                            elide: Text.ElideRight
                                            width: Math.max(90, Math.min(160, appsBottomBar.width * 0.25))
                                            height: 20
                                            verticalAlignment: Text.AlignVCenter
                                        }

                                        Label {
                                            id: bottomBarAppPath
                                            text: appsBottomBar.currentApp.path || ""
                                            font.pixelSize: 10
                                            color: desk.muted
                                            elide: Text.ElideMiddle
                                            width: Math.max(0, appShortcuts.width - bottomBarAppName.width - 290)
                                            visible: width >= 40
                                            height: 20
                                            verticalAlignment: Text.AlignVCenter
                                            Layout.minimumWidth: 0
                                            opacity: 0.75
                                        }

                                        KeycapBadge {
                                            objectName: "appOpenAction"
                                            keyText: "↵"
                                            labelText: appsBottomBar.width < 400 ? "Mở" : "Mở ứng dụng"
                                            Accessible.name: "Mở ứng dụng đã chọn, Enter"
                                            primary: true
                                            Layout.alignment: Qt.AlignVCenter
                                            onClicked: {
                                                desk.liveController.launchApplication(appsBottomBar.currentApp.path)
                                                var restored = desk.liveController.closeAppsView()
                                                if (restored) editor.text = restored
                                            }
                                        }

                                        KeycapBadge {
                                            keyText: "⌘↵"
                                            labelText: "Finder"
                                            Layout.alignment: Qt.AlignVCenter
                                            onClicked: {
                                                desk.liveController.revealInFinder(appsBottomBar.currentApp.path)
                                            }
                                        }

                                        KeycapBadge {
                                            keyText: "Esc"
                                            labelText: "Quay lại"
                                            Layout.alignment: Qt.AlignVCenter
                                            onClicked: {
                                                var restored = desk.liveController.closeAppsView()
                                                if (restored) editor.text = restored
                                                editor.forceActiveFocus()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        visible: desk.liveSnapshot.nextPage > 0
                        Layout.fillWidth: true
                        QuietButton { objectName: "nextBatch"; visible: desk.liveSnapshot.nextPage > 0; text: "Tìm tiếp từ trang " + desk.liveSnapshot.nextPage; onClicked: desk.liveController.nextBatch() }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        QuietButton {
                            objectName: "logToggle"
                            text: desk.logOpen ? "⌄  Chi tiết & nhật ký" : "›  Chi tiết & nhật ký"
                            font.pixelSize: 11
                            leftPadding: 0
                            topPadding: 4
                            bottomPadding: 4
                            onClicked: desk.logOpen = !desk.logOpen
                        }
                        Item { Layout.fillWidth: true }
                    }
                    Label { visible: desk.logOpen && desk.liveSnapshot.view === "page"; text: desk.liveSnapshot.status || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true }
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
            y: composer.y - height + (desk.hasAnswerPreview ? 12 : 7)
            width: desk.hasAnswerPreview ? Math.min(360, composer.width - x) : Math.min(228, composer.width - x)
            height: desk.hasAnswerPreview ? Math.max(76, Math.min(112, minPreviewContent.implicitHeight + topPadding + bottomPadding)) : desk.noticeVisible ? 61 : 48
            rotation: -1.2
            z: 3
            Accessible.name: desk.hasAnswerPreview ? (desk.noticeVisible ? "Kết quả mới. " : "") + desk.previewMeta + ". " + desk.previewBody + ". Mở câu trả lời đầy đủ" : desk.noticeVisible ? "Có kết quả mới, mở workbench" : "Mở lại workbench"
            onClicked: desk.openWorkbench()
            background: Rectangle {
                radius: 12
                color: note.hovered ? desk.backingColor : desk.paperColor
                border.width: note.visualFocus ? 2 : 1
                border.color: note.visualFocus ? desk.accent : desk.edge
            }
            contentItem: ColumnLayout {
                id: minPreviewContent
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        objectName: "minAnswerExcerpt"
                        Layout.fillWidth: true
                        text: desk.hasAnswerPreview ? desk.previewBody : desk.liveMode && desk.liveSnapshot.errorCode ? "Xem thông báo" : desk.phase === "working" ? "Xem tiến trình" : "Xem kết quả"
                        textFormat: Text.PlainText
                        color: desk.hasAnswerPreview ? desk.ink : desk.accent
                        font.pixelSize: 13
                        font.family: desk.liveSnapshot.answerPreviewIsCode ? "Menlo" : Qt.application.font.family
                        wrapMode: desk.liveSnapshot.answerPreviewIsCode ? Text.NoWrap : Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                    DeskIcon { name: "chevron-up"; color: desk.accent; Layout.preferredWidth: 14; Layout.preferredHeight: 14; Layout.alignment: Qt.AlignTop }
                }
                RowLayout {
                    visible: desk.hasAnswerPreview || desk.noticeVisible
                    Layout.fillWidth: true
                    spacing: 5
                    Rectangle { visible: desk.noticeVisible; implicitWidth: 5; implicitHeight: 5; radius: 3; color: desk.accent }
                    Label {
                        objectName: "minAnswerMetadata"
                        Layout.fillWidth: true
                        text: desk.hasAnswerPreview ? desk.previewMeta : "Kết quả mới"
                        textFormat: Text.PlainText
                        font.pixelSize: 10
                        color: desk.incompletePreview || desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                }
            }
            topPadding: desk.hasAnswerPreview ? 10 : 6
            bottomPadding: desk.hasAnswerPreview ? 22 : 17
            leftPadding: 16
            rightPadding: 16
        }
        Item {
            id: mascotItem
            objectName: "mascotCrop"
            x: 4
            y: composer.y - 116 + (mascotWobble.running ? mascotWobble.offsetY : 0)
            width: 122
            height: 116
            clip: true
            z: 4
            rotation: mascotWobble.running ? mascotWobble.rot : 0
            Image {
                width: 180
                height: width * (sourceSize.height / Math.max(1, sourceSize.width))
                source: desk.mascotSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                Accessible.ignored: true
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: mascotWobble.restart()
            }
            SequentialAnimation {
                id: mascotWobble
                property real offsetY: 0
                property real rot: 0
                NumberAnimation { target: mascotWobble; property: "offsetY"; from: 0; to: -6; duration: 80; easing.type: Easing.OutQuad }
                NumberAnimation { target: mascotWobble; property: "rot"; from: 0; to: 3; duration: 60 }
                NumberAnimation { target: mascotWobble; property: "rot"; from: 3; to: -3; duration: 80 }
                NumberAnimation { target: mascotWobble; property: "rot"; from: -3; to: 0; duration: 60 }
                NumberAnimation { target: mascotWobble; property: "offsetY"; from: -6; to: 0; duration: 100; easing.type: Easing.OutBounce }
            }
        }
        Rectangle {
            id: composer
            objectName: "composer"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            height: desk.phase === "startup" ? 94 : Math.min(148, Math.max(94, editorColumn.implicitHeight + 18))
            radius: 18
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
                    sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang chuẩn bị giao diện" }
                }
            }
            ColumnLayout {
                id: editorColumn
                visible: desk.phase !== "startup"
                x: 14
                y: 13
                width: parent.width - 28
                spacing: 7

                // One document control in both folded and expanded modes.
                Rectangle {
                    id: contextChip
                    objectName: "contextChip"
                    visible: Boolean(desk.liveSnapshot.activeContext)
                    implicitHeight: 28
                    implicitWidth: Math.min(chipRow.implicitWidth + 8, editorColumn.width)
                    Layout.maximumWidth: editorColumn.width
                    radius: 7
                    color: desk.utilitySurface
                    RowLayout {
                        id: chipRow
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 2
                        QuietButton {
                            id: documentButton
                            objectName: "documentMenu"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: desk.liveSnapshot.activeContext ? (desk.liveSnapshot.activeContext.title + " · " + desk.liveSnapshot.activeContext.subtitle) : ""
                            iconName: desk.liveSnapshot.fileName ? "pdf" : "file"
                            trailingIconName: desk.liveSnapshot.fileName ? "chevron-down" : ""
                            iconSize: 14
                            elideText: true
                            font.pixelSize: 11
                            topPadding: 2
                            bottomPadding: 2
                            leftPadding: 4
                            rightPadding: 4
                            Accessible.name: "Tài liệu đang chọn: " + text + (desk.liveSnapshot.fileName ? ", mở thao tác PDF" : "")
                            enabled: Boolean(desk.liveSnapshot.fileName)
                            onClicked: documentPopup.open()
                            ToolTip.visible: hovered
                            ToolTip.text: desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.title : ""
                        }
                        IconButton {
                            objectName: "clearContext"
                            glyph: "close"
                            iconSize: 12
                            implicitWidth: 22
                            implicitHeight: 22
                            padding: 5
                            Accessible.name: "Bỏ chọn tài liệu đính kèm"
                            onClicked: { if (desk.liveController) desk.liveController.clearActiveContext() }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredHeight: Math.min(contextChip.visible ? 56 : 78, Math.max(30, editor.contentHeight + 4))
                        contentWidth: availableWidth
                        clip: true
                    TextArea {
                        id: editor
                        objectName: "draftEditor"
                        Accessible.name: "Nhập yêu cầu"
                        KeyNavigation.priority: KeyNavigation.BeforeItem
                        KeyNavigation.tab: sendControl
                        padding: 0
                        topPadding: 4
                        font.pixelSize: 15
                        color: desk.ink
                        selectionColor: desk.accent
                        selectedTextColor: desk.accentText
                        placeholderTextColor: desk.muted
                        placeholderText: desk.liveMode ? (
                            desk.liveSnapshot.view === "apps" ? "Tìm ứng dụng…"
                            : (desk.liveSnapshot.fileName ? "Tìm gì trong tài liệu này?" : "Tìm tệp, mở app hoặc hỏi Chuột…")
                        ) : desk.phase === "idle" ? "Chuột nghe đây. Bạn cần gì?" : "Hỏi tiếp hoặc sửa điều gì đó…"
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        background: null
                        onTextChanged: {
                            if (desk.liveMode) {
                                if (desk.liveSnapshot.view === "apps") {
                                    desk.selectedAppGridIndex = 0
                                } else {
                                    desk.selectedFinderIndex = -1
                                }
                                desk.liveController.onComposerTextChanged(text)
                            }
                        }
                        Keys.onDownPressed: event => {
                            if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                var total = desk.filteredApps.length
                                if (total > 0) {
                                    event.accepted = true
                                    var cols = desk.gridColumns
                                    desk.selectedAppGridIndex = Math.min(total - 1, desk.selectedAppGridIndex + cols)
                                    return
                                }
                            }
                            if (desk.liveMode && desk.liveSnapshot.view === "finder") {
                                var hits = desk.liveSnapshot.finderHits || []
                                if (hits.length > 0) {
                                    event.accepted = true
                                    if (desk.selectedFinderIndex < hits.length - 1) {
                                        desk.selectedFinderIndex++
                                    } else {
                                        desk.selectedFinderIndex = 0
                                    }
                                    return
                                }
                            }
                            event.accepted = false
                        }
                        Keys.onUpPressed: event => {
                            if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                var total = desk.filteredApps.length
                                if (total > 0) {
                                    event.accepted = true
                                    var cols = desk.gridColumns
                                    desk.selectedAppGridIndex = Math.max(0, desk.selectedAppGridIndex - cols)
                                    return
                                }
                            }
                            if (desk.liveMode && desk.liveSnapshot.view === "finder") {
                                var hits = desk.liveSnapshot.finderHits || []
                                if (hits.length > 0) {
                                    event.accepted = true
                                    if (desk.selectedFinderIndex > 0) {
                                        desk.selectedFinderIndex--
                                    } else {
                                        desk.selectedFinderIndex = hits.length - 1
                                    }
                                    return
                                }
                            }
                            event.accepted = false
                        }
                        Keys.onLeftPressed: event => {
                            if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                var total = desk.filteredApps.length
                                if (total > 0) {
                                    event.accepted = true
                                    desk.selectedAppGridIndex = Math.max(0, desk.selectedAppGridIndex - 1)
                                    return
                                }
                            }
                            event.accepted = false
                        }
                        Keys.onRightPressed: event => {
                            if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                var total = desk.filteredApps.length
                                if (total > 0) {
                                    event.accepted = true
                                    desk.selectedAppGridIndex = Math.min(total - 1, desk.selectedAppGridIndex + 1)
                                    return
                                }
                            }
                            event.accepted = false
                        }
                        Keys.onEscapePressed: event => {
                            if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                event.accepted = true
                                var restored = desk.liveController.closeAppsView()
                                if (restored) editor.text = restored
                                return
                            }
                            if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                event.accepted = true
                                desk.selectedFinderIndex = -1
                                return
                            }
                            event.accepted = false
                        }
                        Keys.onReturnPressed: event => {
                            if (!inputMethodComposing) {
                                if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                    event.accepted = true
                                    if (desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length) {
                                        var app = desk.filteredApps[desk.selectedAppGridIndex]
                                        if ((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier)) {
                                            desk.liveController.revealInFinder(app.path)
                                        } else {
                                            desk.liveController.launchApplication(app.path)
                                            var restored = desk.liveController.closeAppsView()
                                            if (restored) editor.text = restored
                                        }
                                    }
                                    return
                                }
                                if ((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier)) {
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        event.accepted = true
                                        var idx = desk.selectedFinderIndex
                                        desk.liveController.revealSelectedInFinder(idx)
                                        return
                                    }
                                }
                                if (!(event.modifiers & Qt.ShiftModifier)) {
                                    event.accepted = true
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        var idx = desk.selectedFinderIndex
                                        desk.selectedFinderIndex = -1
                                        desk.liveController.openSelectedHit(idx)
                                    } else {
                                        desk.submitDraft()
                                    }
                                } else {
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        event.accepted = true
                                        var idx = desk.selectedFinderIndex
                                        desk.selectedFinderIndex = -1
                                        desk.liveController.askAboutSelectedHit(idx, editor.text)
                                    } else {
                                        event.accepted = false
                                    }
                                }
                            } else {
                                event.accepted = false
                            }
                        }
                        Keys.onEnterPressed: event => {
                            if (!inputMethodComposing) {
                                if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                    event.accepted = true
                                    if (desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length) {
                                        var app = desk.filteredApps[desk.selectedAppGridIndex]
                                        if ((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier)) {
                                            desk.liveController.revealInFinder(app.path)
                                        } else {
                                            desk.liveController.launchApplication(app.path)
                                            var restored = desk.liveController.closeAppsView()
                                            if (restored) editor.text = restored
                                        }
                                    }
                                    return
                                }
                                if ((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier)) {
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        event.accepted = true
                                        var idx = desk.selectedFinderIndex
                                        desk.liveController.revealSelectedInFinder(idx)
                                        return
                                    }
                                }
                                if (!(event.modifiers & Qt.ShiftModifier)) {
                                    event.accepted = true
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        var idx = desk.selectedFinderIndex
                                        desk.selectedFinderIndex = -1
                                        desk.liveController.openSelectedHit(idx)
                                    } else {
                                        desk.submitDraft()
                                    }
                                } else {
                                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0) {
                                        event.accepted = true
                                        var idx = desk.selectedFinderIndex
                                        desk.selectedFinderIndex = -1
                                        desk.liveController.askAboutSelectedHit(idx, editor.text)
                                    } else {
                                        event.accepted = false
                                    }
                                }
                            } else {
                                event.accepted = false
                            }
                        }
                    }
                    }
                    QuietButton {
                        id: sendControl
                        objectName: "sendButton"
                        text: ""
                        iconName: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy) ? "stop" : (desk.liveMode && desk.liveSnapshot.view === "apps" ? "enter" : "arrow-up")
                        iconSize: 18
                        leftPadding: 8
                        rightPadding: 8
                        Accessible.name: desk.liveMode ? (desk.liveSnapshot.busy ? "Dừng yêu cầu" : (desk.liveSnapshot.view === "apps" ? "Mở ứng dụng đã chọn" : desk.liveSnapshot.fileName ? "Tìm trong PDF" : "Gửi yêu cầu")) : desk.phase === "receiving" ? "Dừng yêu cầu minh họa" : "Gửi yêu cầu minh họa"
                        primary: true
                        implicitWidth: 34
                        implicitHeight: 34
                        Layout.alignment: Qt.AlignTop
                        font.pixelSize: 18
                        onClicked: {
                            if (desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy)) {
                                desk.stopRequest()
                            } else if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                                if (desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length) {
                                    var app = desk.filteredApps[desk.selectedAppGridIndex]
                                    desk.liveController.launchApplication(app.path)
                                    var restored = desk.liveController.closeAppsView()
                                    if (restored) editor.text = restored
                                }
                            } else {
                                desk.submitDraft()
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Label { visible: desk.phase === "idle" && !desk.liveMode; text: "↵ Gửi · ⇧↵ Xuống dòng"; color: desk.muted; font.pixelSize: 11 }
                    Label {
                        visible: desk.liveMode
                        text: "RAT"
                        color: desk.accent
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        padding: 5
                        ToolTip.visible: dragHandle.containsMouse
                        ToolTip.text: "Kéo để di chuyển cửa sổ"
                        MouseArea { id: dragHandle; objectName: "dragHandle"; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.OpenHandCursor; onPressed: desk.moveRequested() }
                    }
                    Label {
                        visible: desk.liveMode && !desk.liveSnapshot.fileName
                        Layout.fillWidth: true
                        text: desk.liveSnapshot.busy && !desk.expanded ? desk.liveSnapshot.status : "Kéo thả PDF"
                        elide: Text.ElideRight
                        color: desk.muted
                        font.pixelSize: 11
                    }
                    Item { visible: desk.liveMode && Boolean(desk.liveSnapshot.fileName); Layout.fillWidth: true }
                    QuietButton {
                        id: appsGridButton
                        objectName: "appsGridButton"
                        visible: desk.liveMode
                        text: "Ứng dụng"
                        highlighted: desk.liveSnapshot.view === "apps"
                        Accessible.name: desk.liveSnapshot.view === "apps" ? "Quay lại bàn làm việc" : "Mở danh mục ứng dụng macOS dạng lưới"
                        onClicked: {
                            if (desk.liveSnapshot.view === "apps") {
                                var restored = desk.liveController.closeAppsView()
                                if (restored) editor.text = restored
                            } else {
                                desk.liveController.openAppsView(editor.text)
                            }
                            editor.forceActiveFocus()
                        }
                    }
                    QuietButton { objectName: "choosePdf"; visible: desk.liveMode; text: desk.liveSnapshot.fileName ? "+ PDF" : "Chọn PDF"; onClicked: pdfDialog.open() }
                    QuietButton { objectName: "closeDesk"; visible: desk.liveMode; text: ""; iconName: "close"; Accessible.name: "Đóng cửa sổ RAT"; onClicked: desk.closeRequested() }
                    Label { visible: desk.phase === "receiving"; text: "Đang nhận yêu cầu…"; color: desk.muted; font.pixelSize: 12 }
                    QuietButton {
                        visible: !desk.liveMode && desk.hasWorkbench
                        text: "Quy chế học vụ"
                        onClicked: { desk.openWorkbench(); desk.sourceOpen = true }
                    }
                    Item { visible: !desk.liveMode; Layout.fillWidth: true }
                }
                Loader {
                    Layout.fillWidth: true
                    active: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy && !desk.expanded)
                    visible: active
                    sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang nhận yêu cầu" }
                }
            }
        }
    }
    Popup {
        id: documentPopup
        objectName: "documentPopup"
        parent: Overlay.overlay
        focus: true
        x: Math.max(16, unit.x + composer.x + 14)
        y: Math.max(12, unit.y + composer.y - implicitHeight - 8)
        width: Math.min(340, desk.width - 48)
        padding: 16
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { radius: 14; color: desk.paperColor; border.color: desk.edge }
        contentItem: ColumnLayout {
            spacing: 10
            Label { text: desk.liveSnapshot.fileName || "PDF"; textFormat: Text.PlainText; color: desk.ink; font.pixelSize: 14; font.weight: Font.Medium; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label { text: "Đi tới trang PDF"; color: desk.muted; font.pixelSize: 12 }
            RowLayout {
                Layout.fillWidth: true
                SpinBox {
                    id: pagePicker
                    objectName: "pagePicker"
                    from: 1; to: desk.liveSnapshot.pageCount || 1
                    editable: true
                    implicitWidth: 115
                    implicitHeight: 34
                    font.pixelSize: 14
                    Accessible.name: "Số trang PDF từ 1"
                    contentItem: TextInput { text: pagePicker.textFromValue(pagePicker.value, pagePicker.locale); font: pagePicker.font; color: desk.ink; horizontalAlignment: Qt.AlignHCenter; verticalAlignment: Qt.AlignVCenter; readOnly: !pagePicker.editable; validator: pagePicker.validator; inputMethodHints: Qt.ImhDigitsOnly }
                    up.indicator: Rectangle { x: pagePicker.width - width; width: 30; height: parent.height; radius: 7; color: pagePicker.up.pressed ? desk.backingColor : "transparent"; Text { anchors.centerIn: parent; text: "+"; color: desk.muted; font.pixelSize: 17 } }
                    down.indicator: Rectangle { width: 30; height: parent.height; radius: 7; color: pagePicker.down.pressed ? desk.backingColor : "transparent"; Text { anchors.centerIn: parent; text: "−"; color: desk.muted; font.pixelSize: 17 } }
                    background: Rectangle { radius: 8; color: desk.inputColor; border.color: pagePicker.activeFocus ? desk.accent : desk.edge }
                }
                Label { text: "/ " + (desk.liveSnapshot.pageCount || 0); color: desk.muted; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                QuietButton { objectName: "readPage"; text: "Đọc trang →"; primary: true; enabled: !desk.liveSnapshot.busy; onClicked: { documentPopup.close(); desk.liveController.readPage(pagePicker.value) } }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
            QuietButton { objectName: "openOriginal"; text: "Mở PDF gốc"; iconName: "external"; onClicked: { documentPopup.close(); desk.liveController.openOriginal() } }
            QuietButton { objectName: "clearPdf"; text: "Bỏ chọn PDF"; iconName: "close"; onClicked: { documentPopup.close(); desk.liveController.selectFile("") } }
        }
    }
    Shortcut {
        sequences: [StandardKey.Close, StandardKey.Quit]
        enabled: desk.liveMode
        onActivated: desk.closeRequested()
    }
    Shortcut {
        sequence: "Escape"
        enabled: desk.liveMode && desk.expanded
        onActivated: {
            if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                if (restored) editor.text = restored
                editor.forceActiveFocus()
            } else if (desk.selectedFinderIndex >= 0) {
                desk.selectedFinderIndex = -1
            } else {
                desk.foldWorkbench()
            }
        }
    }
    Shortcut {
        sequence: "Ctrl+Shift+A"
        enabled: desk.liveMode
        onActivated: {
            if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                if (restored) editor.text = restored
            } else {
                desk.liveController.openAppsView(editor.text)
            }
            editor.forceActiveFocus()
        }
    }
    Shortcut {
        sequence: "Meta+Shift+A"
        enabled: desk.liveMode
        onActivated: {
            if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                if (restored) editor.text = restored
            } else {
                desk.liveController.openAppsView(editor.text)
            }
            editor.forceActiveFocus()
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
    Shortcut {
        sequence: "Ctrl+Y"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
    Shortcut {
        sequence: "Meta+Y"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
}
