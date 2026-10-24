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
        Qt.callLater(function() {
            if (selectedFinderIndex >= 0 && liveSnapshot.view === "finder") {
                var item = finderRepeater.itemAt(selectedFinderIndex)
                var flick = finderListScroll.contentItem
                if (item && flick && finderListScroll.contentHeight > finderListScroll.height) {
                    var maxY = Math.max(0, finderListScroll.contentHeight - finderListScroll.height)
                    var itemTop = item.y
                    var itemBottom = item.y + item.height
                    if (itemTop < flick.contentY) {
                        flick.contentY = Math.max(0, Math.min(maxY, itemTop))
                    } else if (itemBottom > flick.contentY + finderListScroll.height) {
                        flick.contentY = Math.min(maxY, itemBottom - finderListScroll.height)
                    }
                }
            }
        })
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
    readonly property bool cancelledAnswer: hasAnswerPreview && liveSnapshot.answerOutcome === "cancelled"
    readonly property bool emptyCancelledAnswer: cancelledAnswer && !(liveSnapshot.answerText || "").trim().length
    readonly property bool hasPagePreview: liveMode && liveSnapshot.view === "page" && !liveSnapshot.busy && !liveSnapshot.errorCode
    readonly property string pagePreviewTitle: "Đang đọc trang " + liveSnapshot.pageLabel
    readonly property string uiBuildLabel: "Build 2026.10.24.13"
    property string readerDisplayMode: "matched"
    property bool inlineFindOpen: false
    property bool showAllFinderHits: false
    readonly property var allFinderHits: liveSnapshot.finderHits || []
    readonly property var visibleFinderHits: showAllFinderHits ? allFinderHits : allFinderHits.slice(0, 3)
    readonly property int remainingFinderHits: Math.max(0, allFinderHits.length - 3)
    readonly property bool hasLatentFinderHits: liveMode && !liveSnapshot.busy && !liveSnapshot.fileName && liveSnapshot.view !== "finder" && liveSnapshot.view !== "apps" && allFinderHits.length > 0
    readonly property var searchHits: liveSnapshot.items || []
    onVisibleFinderHitsChanged: {
        if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
    }
    onShowAllFinderHitsChanged: {
        if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
    }
    readonly property bool hasFinderPreview: liveMode && liveSnapshot.view === "finder" && allFinderHits.length > 0
    readonly property bool incompletePreview: hasAnswerPreview && liveSnapshot.answerOutcome !== "completed"
    readonly property string previewBody: liveSnapshot.answerExcerpt || (incompletePreview ? (liveSnapshot.status || "Yêu cầu chưa hoàn tất") : "Mở câu trả lời đầy đủ")
    readonly property string previewMeta: incompletePreview ? (liveSnapshot.answerOutcome === "cancelled" ? "Đã dừng · chưa hoàn tất" : "Chưa hoàn tất · mở để xem thông báo")
        : "Xem nhanh" + (liveSnapshot.answerReadScope ? " · " + liveSnapshot.answerReadScope : ((liveSnapshot.answerSources || []).length ? " · " + liveSnapshot.answerSources.length + " tham chiếu" : ""))
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
    readonly property int controlRadius: 10

    signal copyRequested(string text)
    signal moveRequested()
    signal closeRequested()

    function syncLive() {
        if (!liveMode) return
        const next = liveController.snapshot
        if (next.pageNumber !== liveSnapshot.pageNumber) {
            copied = false
            if (matchedExcerptText) matchedExcerptText.deselect()
        }
        if (next.fileName !== liveSnapshot.fileName || next.view !== "page") {
            copied = false
        }
        if (next.fileName !== liveSnapshot.fileName) {
            pagePicker.value = 1
            pdfSearchField.text = ""
        }
        if (next.view === "page" && next.pageNumber) pagePicker.value = next.pageNumber
        if (next.view === "page") {
            readerDisplayMode = "matched"
        }
        if (next.view === "search" && next.searchQuery && !pdfSearchField.activeFocus) pdfSearchField.text = next.searchQuery
        if (next.view !== "finder") {
            selectedFinderIndex = -1
            showAllFinderHits = false
        } else if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
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
    function openPdfSearch() {
        if (!liveMode || !liveSnapshot.fileName) return
        inlineFindOpen = true
        pdfSearchField.forceActiveFocus()
        pdfSearchField.selectAll()
    }
    function openPdfSearchPopup() {
        openPdfSearch()
    }
    function runPdfSearchAction() {
        if (!liveMode || !liveSnapshot.fileName || liveSnapshot.busy) return
        const kw = pdfSearchField.text.trim()
        if (!kw.length) return
        inlineFindOpen = false
        liveController.search(kw)
        editor.forceActiveFocus()
    }
    function isAppsCommand(value) {
        const command = value.trim().toLowerCase()
        return command === "/apps" || command === "ứng dụng" || command === "mở ứng dụng"
    }
    function submitDraft() {
        if (liveMode) {
            if (!liveSnapshot.busy) {
                if (isAppsCommand(editor.text)) {
                    liveController.openAppsView("")
                    if (liveController.snapshot.view === "apps") editor.text = ""
                    editor.forceActiveFocus()
                    return
                }
                liveController.submitQuery(editor.text)
                if (liveController.snapshot.busy) editor.text = ""
                editor.forceActiveFocus()
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
    function handleComposerReturn(event) {
        if (editor.inputMethodComposing) {
            event.accepted = false
            return
        }
        const hasCmdOrCtrl = Boolean((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier))
        const hasShift = Boolean(event.modifiers & Qt.ShiftModifier)

        if (liveMode && liveSnapshot.view === "apps") {
            event.accepted = true
            if (filteredApps.length > 0 && selectedAppGridIndex >= 0 && selectedAppGridIndex < filteredApps.length) {
                var app = filteredApps[selectedAppGridIndex]
                if (hasCmdOrCtrl) {
                    liveController.revealInFinder(app.path)
                } else {
                    liveController.launchApplication(app.path)
                    var restored = liveController.closeAppsView()
                    editor.text = restored
                }
            }
            return
        }

        if (liveMode && liveSnapshot.view === "finder" && selectedFinderIndex >= 0 && selectedFinderIndex < (visibleFinderHits || []).length) {
            var hit = visibleFinderHits[selectedFinderIndex] || ({})
            if (hasCmdOrCtrl) {
                event.accepted = true
                liveController.revealSelectedInFinder(selectedFinderIndex)
                return
            }
            if (!hasShift) {
                event.accepted = true
                var idx = selectedFinderIndex
                selectedFinderIndex = -1
                var isPdf = Boolean(hit.is_pdf)
                liveController.openSelectedHit(idx)
                if (isPdf) {
                    editor.text = ""
                    editor.forceActiveFocus()
                }
                return
            }
            if (!hit.is_pdf) {
                event.accepted = true
                var fileIdx = selectedFinderIndex
                selectedFinderIndex = -1
                liveController.askAboutSelectedHit(fileIdx, editor.text)
                if (liveController.snapshot.busy) editor.text = ""
                return
            }
        }

        if (!hasShift) {
            event.accepted = true
            submitDraft()
        } else {
            event.accepted = false
        }
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
            var sel = "";
            if (desk.liveSnapshot.view === "answer") {
                sel = (answerText && answerText.selectedText) ? answerText.selectedText : "";
            } else if (desk.liveSnapshot.view === "page") {
                if (matchedExcerptText && matchedExcerptText.visible && matchedExcerptText.selectedText) {
                    sel = matchedExcerptText.selectedText;
                } else {
                    sel = desk.liveSnapshot.rawMatchedSnippet || desk.liveSnapshot.matchedSnippet || "";
                }
            }
            liveController.copyCitation(sel);
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
        function onCopyConfirmed(text) {
            desk.copied = true
            copyFeedback.restart()
        }
    }
    FileDialog {
        id: pdfDialog
        title: "Chọn một PDF để tìm và đọc"
        nameFilters: ["PDF (*.pdf *.PDF)"]
        onAccepted: { if (desk.liveMode) desk.liveController.openPdfDocument(String(selectedFile)) }
    }
    DropArea {
        id: pdfDropArea
        anchors.fill: parent
        enabled: desk.liveMode
        onDropped: drop => {
            if (drop.hasUrls && drop.urls.length === 1) {
                desk.liveController.openPdfDocument(String(drop.urls[0]))
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
        property int trailingIconSize: 13
        property color iconColor: "transparent"
        contentItem: RowLayout {
            property color color: control.primary ? desk.accentText : control.highlighted ? desk.accent : desk.muted
            spacing: (control.iconName || control.trailingIconName) && control.text ? 5 : 0
            DeskIcon {
                visible: Boolean(control.iconName)
                name: control.iconName
                color: control.iconColor.a > 0 ? control.iconColor : parent.color
                width: control.iconSize
                height: control.iconSize
                Layout.preferredWidth: control.iconSize
                Layout.preferredHeight: control.iconSize
                Layout.alignment: control.text ? Qt.AlignVCenter : (Qt.AlignHCenter | Qt.AlignVCenter)
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
                width: control.trailingIconSize
                height: control.trailingIconSize
                Layout.preferredWidth: control.trailingIconSize
                Layout.preferredHeight: control.trailingIconSize
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
            Rectangle {
                visible: keycapRoot.keyText.length > 0
                radius: 4
                color: keycapRoot.primary ? Qt.rgba(0.31, 0.40, 0.25, 0.10) : desk.utilitySurface
                border.width: 1
                border.color: desk.edge
                implicitWidth: keyGlyph.implicitWidth + 6
                implicitHeight: 16
                Label {
                    id: keyGlyph
                    anchors.centerIn: parent
                    text: keycapRoot.keyText
                    color: keycapRoot.primary ? desk.accent : desk.muted
                    font.pixelSize: 10
                }
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

    component PdfSnapshotCard: Rectangle {
        id: snapCard
        property bool activeSnapshot: true
        property string pdfPath: ""
        property int pdfPage: 0
        property string matchQuery: ""
        property string matchSnippet: ""
        property int maxCardHeight: 132
        signal activated()

        readonly property string snapshotUrl: (desk.liveMode && activeSnapshot && pdfPath.length > 0 && pdfPage > 0)
            ? desk.liveController.pageSnapshot(pdfPath, pdfPage, matchQuery, matchSnippet)
            : ""
        readonly property bool snapshotReady: snapImage.status === Image.Ready && snapImage.implicitWidth > 0 && snapImage.implicitHeight > 0
        readonly property real targetWidth: Math.max(200, resultScroll.availableWidth - 18)

        visible: activeSnapshot && snapshotUrl.length > 0
        Layout.fillWidth: true
        implicitHeight: snapshotReady
            ? Math.min(maxCardHeight, Math.max(58, Math.round(targetWidth * (snapImage.implicitHeight / Math.max(1, snapImage.implicitWidth))) + 8))
            : 0
        radius: 8
        color: "#fdfdf9"
        border.width: snapMouse.containsMouse ? 1.5 : 1
        border.color: snapMouse.containsMouse ? desk.accent : desk.edge
        clip: true
        Accessible.role: Accessible.Button

        Image {
            id: snapImage
            anchors.fill: parent
            anchors.margins: 4
            source: snapCard.snapshotUrl
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            cache: false
            Accessible.ignored: true
        }

        Rectangle {
            visible: snapMouse.containsMouse
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 6
            radius: 5
            color: Qt.rgba(desk.paperColor.r, desk.paperColor.g, desk.paperColor.b, 0.92)
            border.width: 1
            border.color: desk.selectedEdge
            implicitWidth: openHintLabel.implicitWidth + 10
            implicitHeight: 20
            Label {
                id: openHintLabel
                anchors.centerIn: parent
                text: "Đọc trang " + snapCard.pdfPage + " →"
                color: desk.accent
                font.pixelSize: 10
                font.weight: Font.Medium
            }
        }

        MouseArea {
            id: snapMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: snapCard.activated()
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
            x: resultPaper.x - 6
            y: resultPaper.y - 5
            width: resultPaper.width
            height: resultPaper.height
            radius: 15
            rotation: -0.9
            antialiasing: true
            color: desk.backingColor
            border.width: 1
            border.color: desk.edge
            z: 0
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
            z: 1
            Behavior on y {
                enabled: desk.readyForMotion && !desk.reduceMotion
                NumberAnimation { id: paperMove; duration: 160; easing.type: Easing.OutCubic }
            }
            RowLayout {
                id: liveHeader
                visible: desk.liveMode
                x: 22
                y: 10
                width: parent.width - 44
                spacing: 4
                RowLayout {
                    visible: !desk.liveSnapshot.canBack && desk.liveSnapshot.view !== "apps" && desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "page"
                    spacing: 6
                    Rectangle {
                        implicitWidth: 6
                        implicitHeight: 6
                        radius: 3
                        color: desk.liveSnapshot.view === "answer" ? desk.accent : desk.selectedEdge
                    }
                    Label {
                        text: desk.liveSnapshot.view === "answer" ? (desk.cancelledAnswer ? "Đã dừng yêu cầu" : "Câu trả lời của Chuột")
                            : (desk.liveSnapshot.view === "busy" ? "Đang xử lý" : ("Trong tài liệu · " + (desk.liveSnapshot.fileName || "PDF")))
                        elide: Text.ElideMiddle
                        Layout.maximumWidth: Math.min(215, Math.max(80, resultPaper.width - 150))
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: desk.muted
                    }
                }
                QuietButton {
                    objectName: "backToAnswer"
                    visible: desk.liveSnapshot.view === "page" && Boolean(desk.liveSnapshot.canBackToAnswer)
                    text: resultPaper.width < 400 ? "" : "Câu trả lời"
                    iconName: "arrow-left"
                    iconSize: 14
                    leftPadding: 6
                    rightPadding: resultPaper.width < 400 ? 6 : 9
                    Accessible.name: "Quay lại câu trả lời vừa xem"
                    onClicked: desk.liveController.backToAnswer()
                }
                QuietButton {
                    objectName: "backToSearch"
                    visible: Boolean(desk.liveSnapshot.canBack)
                    text: resultPaper.width < 400 ? "" : "Kết quả"
                    iconName: "arrow-left"
                    iconSize: 14
                    leftPadding: 6
                    rightPadding: resultPaper.width < 400 ? 6 : 9
                    onClicked: desk.liveController.backToSearch()
                }
                QuietButton {
                    objectName: "backFromApps"
                    visible: desk.liveSnapshot.view === "apps"
                    text: "Bàn làm việc"
                    iconName: "arrow-left"
                    iconSize: 14
                    leftPadding: 6
                    onClicked: {
                        var restored = desk.liveController.closeAppsView()
                        editor.text = restored
                        editor.forceActiveFocus()
                    }
                }
                QuietButton {
                    id: backFromFinderButton
                    objectName: "backFromFinder"
                    visible: desk.liveSnapshot.view === "finder"
                    text: Boolean(desk.liveSnapshot.answerText) ? "Câu trả lời" : "Bàn làm việc"
                    iconName: "arrow-left"
                    iconSize: 14
                    leftPadding: 6
                    Accessible.name: Boolean(desk.liveSnapshot.answerText) ? "Quay lại câu trả lời và đóng gợi ý" : "Quay lại bàn làm việc và đóng gợi ý"
                    onClicked: {
                        desk.liveController.dismissFinder()
                        editor.forceActiveFocus()
                    }
                }

                RowLayout {
                    id: pageNavCluster
                    visible: desk.liveSnapshot.view === "page"
                    spacing: 2

                    IconButton {
                        objectName: "prevPage"
                        glyph: "chevron-left"
                        iconSize: 11
                        implicitWidth: 18
                        implicitHeight: 20
                        padding: 2
                        enabled: !desk.liveSnapshot.busy && (desk.liveSnapshot.pageNumber || 1) > 1
                        Accessible.name: "Trang trước"
                        onClicked: { if (desk.liveController) desk.liveController.prevPage() }
                        ToolTip.visible: hovered
                        ToolTip.text: "Trang trước"
                    }
                    SpinBox {
                        id: pagePicker
                        objectName: "pagePicker"
                        from: 1
                        to: Math.max(1, desk.liveSnapshot.pageCount || 1)
                        value: desk.liveSnapshot.pageNumber || 1
                        editable: true
                        implicitWidth: 38
                        implicitHeight: 20
                        font.pixelSize: 11
                        Accessible.name: "Số trang PDF"
                        contentItem: TextInput {
                            text: pagePicker.textFromValue(pagePicker.value, pagePicker.locale)
                            font: pagePicker.font
                            color: desk.ink
                            horizontalAlignment: Qt.AlignHCenter
                            verticalAlignment: Qt.AlignVCenter
                            readOnly: !pagePicker.editable
                            validator: pagePicker.validator
                            inputMethodHints: Qt.ImhDigitsOnly
                            onAccepted: {
                                if (desk.liveController && !desk.liveSnapshot.busy) {
                                    desk.liveController.readPage(pagePicker.value)
                                }
                            }
                        }
                        up.indicator: Item {}
                        down.indicator: Item {}
                        background: Rectangle {
                            radius: 4
                            color: desk.utilitySurface
                            border.color: pagePicker.activeFocus ? desk.accent : desk.edge
                        }
                        onValueModified: {
                            if (desk.liveController && !desk.liveSnapshot.busy) {
                                desk.liveController.readPage(value)
                            }
                        }
                    }
                    Label {
                        text: "/ " + (desk.liveSnapshot.pageCount || 0)
                        color: desk.muted
                        font.pixelSize: 11
                    }
                    IconButton {
                        objectName: "nextPage"
                        glyph: "chevron-right"
                        iconSize: 11
                        implicitWidth: 18
                        implicitHeight: 20
                        padding: 2
                        enabled: !desk.liveSnapshot.busy && (desk.liveSnapshot.pageNumber || 1) < (desk.liveSnapshot.pageCount || 1)
                        Accessible.name: "Trang kế tiếp"
                        onClicked: { if (desk.liveController) desk.liveController.nextPage() }
                        ToolTip.visible: hovered
                        ToolTip.text: "Trang sau"
                    }
                    IconButton {
                        objectName: "readPage"
                        glyph: "arrow-right"
                        iconSize: 11
                        implicitWidth: 18
                        implicitHeight: 20
                        padding: 2
                        enabled: !desk.liveSnapshot.busy
                        Accessible.name: "Đọc trang đã chọn"
                        onClicked: { if (desk.liveController) desk.liveController.readPage(pagePicker.value) }
                        ToolTip.visible: hovered
                        ToolTip.text: "Đọc trang"
                    }

                    IconButton {
                        objectName: "openPdfSearchInPage"
                        visible: resultPaper.width >= 420
                        glyph: "search"
                        iconSize: 12
                        implicitWidth: 20
                        implicitHeight: 20
                        padding: 3
                        Accessible.name: "Tìm từ khóa trong PDF (⌘F)"
                        onClicked: desk.openPdfSearch()
                        ToolTip.visible: hovered
                        ToolTip.text: "Tìm chữ (⌘F)"
                    }

                    IconButton {
                        objectName: "openOriginal"
                        visible: resultPaper.width >= 420
                        glyph: "external"
                        iconSize: 12
                        implicitWidth: 20
                        implicitHeight: 20
                        padding: 3
                        Accessible.name: "Mở PDF gốc"
                        onClicked: { if (desk.liveController) desk.liveController.openOriginal() }
                        ToolTip.visible: hovered
                        ToolTip.text: "Mở PDF gốc"
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 2
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.OpenHandCursor
                        onPressed: desk.moveRequested()
                    }
                }
                QuietButton {
                    objectName: "copyCitation"
                    visible: Boolean(desk.liveSnapshot.canCopy)
                    text: desk.copied ? "Đã chép" : (desk.liveSnapshot.view === "page" ? "Chép đoạn" : (desk.liveSnapshot.view === "answer" ? (resultPaper.width < 360 ? "Chép" : "Sao chép") : (resultPaper.width < 450 ? "Chép" : "Chép trích dẫn")))
                    iconName: desk.copied ? "check" : "copy"
                    leftPadding: resultPaper.width < 360 ? 5 : 8
                    rightPadding: resultPaper.width < 360 ? 5 : 8
                    font.pixelSize: 11
                    onClicked: desk.requestCopy()
                }
                QuietButton {
                    objectName: "liveFoldButton"
                    text: ""
                    iconName: "minus"
                    leftPadding: 6
                    rightPadding: 6
                    Accessible.name: "Thu workbench"
                    onClicked: desk.foldWorkbench()
                }
            }
            Rectangle {
                visible: desk.liveMode
                x: 22
                y: 42
                width: parent.width - 44
                height: 1
                color: desk.edge
                opacity: 0.75
            }
            Rectangle {
                visible: desk.liveMode && desk.liveSnapshot.view !== "finder" && resultScroll.contentHeight > resultScroll.height + 4 && (!resultScroll.contentItem || resultScroll.contentItem.contentY + resultScroll.height < resultScroll.contentHeight - 6)
                x: 22
                y: resultScroll.y + resultScroll.height - 22
                width: parent.width - 52
                height: 22
                z: 4
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.75; color: Qt.rgba(desk.paperColor.r, desk.paperColor.g, desk.paperColor.b, 0.88) }
                    GradientStop { position: 1.0; color: desk.paperColor }
                }
            }
            ScrollView {
                id: resultScroll
                objectName: "resultScroll"
                x: 22
                y: desk.liveMode ? ((desk.inlineFindOpen && desk.expanded) ? 86 : 46) : 16
                width: parent.width - 44
                height: Math.max(0, parent.height - (desk.liveMode ? ((desk.inlineFindOpen && desk.expanded) ? 120 : 80) : 38))
                contentWidth: availableWidth
                contentHeight: resultContents.implicitHeight
                clip: true
                ScrollBar.vertical: ScrollBar {
                    parent: resultScroll
                    x: resultScroll.width - width
                    y: 2
                    height: resultScroll.availableHeight - 4
                    width: 4
                    policy: (resultScroll.contentHeight > resultScroll.height && desk.liveSnapshot.view !== "finder") ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: desk.selectedEdge
                        opacity: 0.85
                    }
                    background: Item {}
                }
            ColumnLayout {
                id: resultContents
                width: resultScroll.availableWidth - ((resultScroll.contentHeight > resultScroll.height && desk.liveSnapshot.view !== "finder") ? 10 : 0)
                spacing: 6
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
                RowLayout {
                    visible: desk.liveMode && desk.liveSnapshot.view === "page"
                    Layout.fillWidth: true
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1

                        Label {
                            id: pageSourceTitle
                            objectName: "pageSourceTitle"
                            Layout.fillWidth: true
                            text: (desk.liveSnapshot.sourceKind === "search_hit" || Boolean(desk.liveSnapshot.hasMatchedSnippet))
                                ? ("Nguồn · Trang " + (desk.liveSnapshot.pageNumber || 1))
                                : ("Nguồn · Trang " + (desk.liveSnapshot.pageNumber || 1) + "/" + (desk.liveSnapshot.pageCount || 1))
                            textFormat: Text.PlainText
                            color: desk.ink
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Label {
                            id: pageMetaLabel
                            objectName: "pageMetadataLabel"
                            Layout.fillWidth: true
                            text: desk.liveSnapshot.fileName || ""
                            textFormat: Text.PlainText
                            elide: Text.ElideMiddle
                            color: desk.muted
                            font.pixelSize: 11
                            ToolTip.visible: pageMetaMouse.containsMouse
                            ToolTip.text: desk.liveSnapshot.fileName || ""
                            MouseArea {
                                id: pageMetaMouse
                                anchors.fill: parent
                                hoverEnabled: true
                            }
                        }
                    }

                    QuietButton {
                        id: openOriginalExternal
                        objectName: "openOriginalExternal"
                        text: resultPaper.width < 420 ? "PDF gốc" : "Mở PDF gốc"
                        iconName: "external"
                        font.pixelSize: 11
                        leftPadding: 6
                        rightPadding: 8
                        Accessible.name: "Mở PDF gốc bằng ứng dụng ngoài"
                        onClicked: { if (desk.liveController) desk.liveController.openOriginal() }
                    }
                }
                Label {
                    visible: !desk.liveMode || (desk.liveSnapshot.view !== "answer" && desk.liveSnapshot.view !== "page")
                    Layout.fillWidth: true
                    text: desk.liveMode ? (
                        desk.liveSnapshot.view === "finder" ? (desk.liveSnapshot.title || "Gợi ý tìm kiếm")
                        : (desk.liveSnapshot.view === "apps" ? ("Ứng dụng (" + desk.filteredApps.length + ")")
                        : (desk.liveSnapshot.title || "Đang mở bàn làm việc…"))
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
                    spacing: desk.emptyCancelledAnswer ? 8 : 12
                    ColumnLayout {
                        visible: desk.liveSnapshot.view === "answer"
                        Layout.fillWidth: true
                        spacing: 8
                        Rectangle {
                            id: answerQuestionCard
                            objectName: "answerQuestionCard"
                            Layout.fillWidth: true
                            implicitHeight: questionCardCol.implicitHeight + 18
                            radius: desk.cardRadius
                            color: desk.utilitySurface
                            border.width: answerQuestion.visualFocus ? 1.5 : 1
                            border.color: answerQuestion.visualFocus ? desk.accent : desk.edge

                            Rectangle {
                                x: 0
                                y: 8
                                width: 3.5
                                height: Math.max(14, parent.height - 16)
                                radius: 2
                                color: desk.accent
                            }

                            ColumnLayout {
                                id: questionCardCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.leftMargin: 13
                                anchors.rightMargin: 11
                                anchors.topMargin: 8
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Label {
                                        text: "BẠN HỎI"
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.5
                                        color: desk.accent
                                    }
                                    Item { Layout.fillWidth: true }
                                    DeskIcon {
                                        visible: (desk.liveSnapshot.userQuery || "").length > 48
                                        name: desk.answerQuestionOpen ? "chevron-up" : "chevron-down"
                                        color: desk.muted
                                        width: 12
                                        height: 12
                                    }
                                }

                                Button {
                                    id: answerQuestion
                                    objectName: "answerQuestion"
                                    Layout.fillWidth: true
                                    padding: 0
                                    leftPadding: 0
                                    rightPadding: 0
                                    hoverEnabled: true
                                    Accessible.name: "Câu hỏi: " + (desk.liveSnapshot.userQuery || "")
                                    Accessible.description: "Mở hoặc thu câu hỏi đầy đủ"
                                    onClicked: desk.answerQuestionOpen = !desk.answerQuestionOpen
                                    contentItem: Label {
                                        leftPadding: 0
                                        text: desk.liveSnapshot.userQuery || ""
                                        textFormat: Text.PlainText
                                        font.pixelSize: 14
                                        font.weight: Font.Medium
                                        color: desk.ink
                                        wrapMode: desk.answerQuestionOpen ? Text.Wrap : Text.NoWrap
                                        elide: desk.answerQuestionOpen ? Text.ElideNone : Text.ElideRight
                                    }
                                    background: Item {}
                                    ToolTip.visible: hovered
                                    ToolTip.text: desk.liveSnapshot.userQuery || ""
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Label {
                                text: "CHUỘT TRẢ LỜI"
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.5
                                color: desk.muted
                            }
                            Label {
                                visible: Boolean(answerStatus.text)
                                text: "·"
                                font.pixelSize: 11
                                color: desk.muted
                                opacity: 0.7
                            }
                            Label {
                                id: answerStatus
                                objectName: "answerStatus"
                                visible: Boolean(text)
                                Layout.fillWidth: true
                                text: (desk.liveSnapshot.answerReadScope ? desk.liveSnapshot.answerReadScope + " · " : "") + (desk.liveSnapshot.status || "")
                                textFormat: Text.PlainText
                                wrapMode: Text.NoWrap
                                elide: Text.ElideRight
                                color: desk.muted
                                font.pixelSize: 11
                            }
                            Item { visible: !Boolean(answerStatus.text); Layout.fillWidth: true }
                            Rectangle {
                                visible: desk.liveSnapshot.answerVerification === "PASS" || desk.liveSnapshot.answerVerification === "FAIL"
                                radius: 5
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? Qt.rgba(desk.warningInk.r, desk.warningInk.g, desk.warningInk.b, 0.14) : desk.selectedSurface
                                border.width: 1
                                border.color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.selectedEdge
                                implicitWidth: verifBadgeLabel.implicitWidth + 10
                                implicitHeight: 18
                                Label {
                                    id: verifBadgeLabel
                                    anchors.centerIn: parent
                                    text: desk.liveSnapshot.answerVerification === "PASS" ? "✓ Đạt kiểm tra" : "! Chưa đạt"
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.accent
                                }
                            }
                        }
                    }
                    TextArea {
                        id: answerText
                        objectName: "answerText"
                        visible: desk.liveSnapshot.view === "answer" && !desk.emptyCancelledAnswer
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
                        visible: desk.liveSnapshot.view === "answer" && !desk.emptyCancelledAnswer
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
                                iconSize: 13
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
                                ColumnLayout {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    spacing: 6
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        DeskIcon { name: "file"; color: desk.muted; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                                        Label {
                                            text: modelData.title + (modelData.readScope ? " · " + modelData.readScope : "")
                                            textFormat: Text.PlainText
                                            font.pixelSize: 12
                                            color: desk.muted
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                        QuietButton {
                                            objectName: "openAnswerSource_" + index
                                            visible: true
                                            enabled: Boolean(modelData.canOpen)
                                            text: modelData.label || (modelData.page > 0 ? ("Trang " + modelData.page) : "Chưa xác định trang")
                                            Accessible.name: (modelData.canOpen ? "Đọc trang " : "Tham chiếu: ") + text + ", " + modelData.title
                                            topPadding: 4
                                            bottomPadding: 4
                                            onClicked: {
                                                if (modelData.canOpen) desk.liveController.openAnswerSource(index)
                                            }
                                        }
                                    }
                                    PdfSnapshotCard {
                                        objectName: "sourceSnapshot_" + index
                                        activeSnapshot: desk.answerSourcesOpen && Boolean(modelData.canOpen)
                                        pdfPath: modelData.path || ""
                                        pdfPage: modelData.page || 0
                                        matchQuery: ""
                                        matchSnippet: modelData.snippet || ""
                                        maxCardHeight: 108
                                        Accessible.name: "Ảnh chụp tham chiếu trang PDF " + modelData.page + ", bấm để đọc trang"
                                        onActivated: desk.liveController.openAnswerSource(index)
                                    }
                                }
                            }
                        }
                    }
                    Label {
                        visible: desk.liveSnapshot.view !== "answer" && desk.liveSnapshot.view !== "busy" && desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "apps" && (desk.liveSnapshot.view !== "page" || desk.readerDisplayMode === "text" || desk.liveSnapshot.pageTruncated)
                        Layout.fillWidth: true
                        text: desk.liveSnapshot.view === "page" ? ((desk.liveSnapshot.pageTruncated ? "Đã cắt ở 8.000 ký tự. " : "") + (desk.readerDisplayMode === "text" ? "Bôi chọn đoạn cần lấy, rồi chép trích dẫn." : "")) : (desk.liveSnapshot.view === "error" ? desk.liveSnapshot.errorText : desk.liveSnapshot.status) || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: desk.muted
                        font.pixelSize: 12
                    }
                    Loader {
                        Layout.fillWidth: true
                        active: desk.liveMode && desk.liveSnapshot.busy
                        visible: active
                        sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang xử lý yêu cầu" }
                    }
                    Repeater {
                        model: desk.searchHits
                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 6
                            Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: (modelData.page_label && String(modelData.page_label) !== String(modelData.page)) ? ("Trang " + modelData.page + " · nhãn " + modelData.page_label) : ("Trang " + modelData.page); textFormat: Text.PlainText; color: desk.accent; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                QuietButton { objectName: "readHit_" + modelData.page; text: "Đọc trang"; trailingIconName: "arrow-right"; trailingIconSize: 12; onClicked: { desk.readerDisplayMode = "matched"; desk.liveController.openSearchHit(modelData.page) } }
                            }
                            PdfSnapshotCard {
                                id: hitSnapshotCard
                                objectName: "searchSnapshot_" + modelData.page
                                activeSnapshot: desk.liveSnapshot.view === "search"
                                pdfPath: modelData.path || ""
                                pdfPage: modelData.page || 0
                                matchQuery: desk.liveSnapshot.searchQuery || ""
                                matchSnippet: modelData.snippet || ""
                                maxCardHeight: 132
                                Accessible.name: "Ảnh chụp đoạn khớp tại trang PDF " + modelData.page + ", bấm để đọc trang"
                                onActivated: { desk.readerDisplayMode = "matched"; desk.liveController.openSearchHit(modelData.page) }
                            }
                            Label {
                                visible: !hitSnapshotCard.snapshotReady && text !== ""
                                text: String(modelData.snippet || "").replace(/\s+/g, " ").trim()
                                textFormat: Text.PlainText
                                color: desk.muted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                    Rectangle {
                        id: matchedExcerptWrapper
                        objectName: "matchedExcerptWrapper"
                        visible: desk.liveSnapshot.view === "page"
                        Layout.fillWidth: true
                        implicitHeight: matchedExcerptLayout.implicitHeight + 24
                        radius: 8
                        color: "#fdfdf9"
                        border.width: 1
                        border.color: desk.selectedEdge
                        clip: true

                        ColumnLayout {
                            id: matchedExcerptLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 8

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Rectangle {
                                        implicitWidth: 6
                                        implicitHeight: 6
                                        radius: 3
                                        color: desk.accent
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: desk.liveSnapshot.hasMatchedSnippet
                                            ? ("Đoạn khớp với từ khóa \"" + (desk.liveSnapshot.matchedQuery || desk.liveSnapshot.searchQuery || "") + "\"")
                                            : "Đoạn nguồn"
                                        font.pixelSize: 11
                                        font.weight: Font.Medium
                                        color: desk.accent
                                        wrapMode: Text.Wrap
                                    }
                                }

                                Label {
                                    visible: Boolean(desk.liveSnapshot.hasMatchedSnippet && desk.liveSnapshot.matchedSnippetTruncated)
                                    Layout.leftMargin: 12
                                    text: "Trích đoạn (…)"
                                    font.pixelSize: 10
                                    color: desk.muted
                                }
                            }

                            TextArea {
                                id: matchedExcerptText
                                objectName: "matchedExcerptText"
                                visible: Boolean(desk.liveSnapshot.hasMatchedSnippet)
                                Layout.fillWidth: true
                                Layout.preferredHeight: contentHeight + 6
                                readOnly: true
                                selectByMouse: true
                                persistentSelection: true
                                wrapMode: TextEdit.Wrap
                                textFormat: TextEdit.RichText
                                property string snippetKey: ""
                                Component.onCompleted: {
                                    snippetKey = desk.liveSnapshot.matchedSnippetHtml || ""
                                    text = snippetKey
                                }
                                Connections {
                                    target: desk
                                    function onLiveSnapshotChanged() {
                                        var nextSnippet = desk.liveSnapshot.matchedSnippetHtml || ""
                                        if (matchedExcerptText.snippetKey !== nextSnippet) {
                                            matchedExcerptText.snippetKey = nextSnippet
                                            matchedExcerptText.text = nextSnippet
                                        }
                                    }
                                }
                                color: desk.ink
                                font.pixelSize: 13
                                background: null
                                padding: 0
                                Accessible.name: "Đoạn khớp từ kết quả tìm kiếm"
                            }

                            Label {
                                visible: Boolean(desk.liveSnapshot.hasMatchedSnippet)
                                text: "Bôi chọn phần cần lấy hoặc bấm Chép đoạn để sao chép cả đoạn nguồn."
                                font.pixelSize: 11
                                color: desk.muted
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            ColumnLayout {
                                visible: !desk.liveSnapshot.hasMatchedSnippet
                                Layout.fillWidth: true
                                spacing: 8

                                Label {
                                    text: "Chưa có đoạn trích cho trang này."
                                    font.pixelSize: 12
                                    color: desk.muted
                                }
                                QuietButton {
                                    objectName: "openOriginalFallback"
                                    text: "Mở PDF gốc"
                                    iconName: "external"
                                    font.pixelSize: 11
                                    leftPadding: 6
                                    rightPadding: 8
                                    Accessible.name: "Mở PDF gốc bằng ứng dụng ngoài"
                                    onClicked: { if (desk.liveController) desk.liveController.openOriginal() }
                                }
                            }
                        }
                    }
                    Rectangle {
                        id: visualPageWrapper
                        objectName: "visualPageWrapper"
                        visible: desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "visual"
                        Layout.fillWidth: true
                        implicitHeight: visualPdfPage.status === Image.Ready && visualPdfPage.implicitWidth > 0
                            ? Math.round(width * (visualPdfPage.implicitHeight / Math.max(1, visualPdfPage.implicitWidth))) + 8
                            : 320
                        radius: 8
                        color: "#fdfdf9"
                        border.width: 1
                        border.color: desk.edge
                        clip: true

                        Image {
                            id: visualPdfPage
                            objectName: "visualPdfPage"
                            anchors.fill: parent
                            anchors.margins: 4
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            mipmap: true
                            source: (desk.liveMode && desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "visual" && desk.liveSnapshot.pageNumber > 0)
                                ? desk.liveController.fullPageSnapshot(desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.path : "", desk.liveSnapshot.pageNumber, 1200)
                                : ""
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: visualPdfPage.status !== Image.Ready
                            text: visualPdfPage.status === Image.Loading ? "Đang dựng trang PDF…" : (desk.liveSnapshot.errorCode ? desk.liveSnapshot.errorText : "Đang tải trang…")
                            color: desk.muted
                            font.pixelSize: 12
                        }
                    }

                    TextArea {
                        id: pageText
                        objectName: "pageText"
                        visible: desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "text"
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight + 14
                        bottomPadding: 14
                        text: desk.liveSnapshot.pageReadingText || desk.liveSnapshot.pageText || ""
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
                        visible: desk.liveSnapshot.view === "finder" && (desk.allFinderHits || []).length > 0
                        Layout.fillWidth: true
                        spacing: 6

                        ScrollView {
                            id: finderListScroll
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(finderListColumn.implicitHeight, 206)
                            contentWidth: availableWidth
                            contentHeight: finderListColumn.implicitHeight
                            clip: true
                            ColumnLayout {
                                id: finderListColumn
                                width: finderListScroll.availableWidth - (finderListScroll.contentHeight > finderListScroll.height ? 10 : 0)
                                spacing: 4

                        Repeater {
                            id: finderRepeater
                            model: desk.visibleFinderHits
                            ColumnLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                spacing: 4

                                // Section header when category changes
                                Label {
                                    visible: Boolean(modelData.is_first_of_section)
                                        && (desk.allFinderHits || []).some(function(hit) { return hit.kind !== modelData.kind })
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
                                    color: hitCard.isSelected ? desk.selectedSurface : (hitMouseArea.containsMouse ? desk.hoverSurface : "transparent")
                                    border.color: hitCard.isSelected ? desk.selectedEdge : (hitMouseArea.containsMouse ? desk.edge : "transparent")
                                    border.width: hitCard.isSelected ? 1.5 : 1
                                    Accessible.name: modelData.title + ", " + (modelData.kind === "application" ? "Ứng dụng" : (modelData.is_pdf ? "PDF" : "Tệp")) + " tại " + (modelData.display_path || modelData.path) + ". Chọn để mở"

                                    MouseArea {
                                        id: hitMouseArea
                                        anchors.fill: parent
                                        z: 0
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
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
                                        anchors.topMargin: 7
                                        anchors.bottomMargin: 7
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 10

                                        Item {
                                            Layout.preferredWidth: 28
                                            Layout.preferredHeight: 28
                                            Layout.alignment: Qt.AlignVCenter
                                            Image {
                                                anchors.centerIn: parent
                                                visible: modelData.kind === "application"
                                                width: 28; height: 28
                                                source: visible && modelData.path ? "image://icon/" + modelData.path : ""
                                                sourceSize.width: 56; sourceSize.height: 56
                                                fillMode: Image.PreserveAspectFit
                                                smooth: true
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                visible: modelData.kind !== "application"
                                                radius: 7
                                                color: hitCard.isSelected ? desk.paperColor : desk.utilitySurface
                                                border.width: 1
                                                border.color: desk.edge
                                                DeskIcon {
                                                    anchors.centerIn: parent
                                                    name: modelData.is_pdf ? "pdf" : "file"
                                                    color: modelData.is_pdf ? desk.pdfInk : desk.muted
                                                    width: 17; height: 17
                                                }
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: 2

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8

                                                Label {
                                                    objectName: "finderTitle_" + index
                                                    text: modelData.title
                                                    textFormat: Text.PlainText
                                                    color: desk.ink
                                                    font.pixelSize: 13
                                                    font.weight: Font.Medium
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                Rectangle {
                                                    id: kindBadge
                                                    radius: 4
                                                    color: desk.backingColor
                                                    implicitHeight: 18
                                                    implicitWidth: kindText.implicitWidth + 10
                                                    Layout.alignment: Qt.AlignVCenter
                                                    Label {
                                                        id: kindText
                                                        anchors.centerIn: parent
                                                        text: modelData.kind === "application" ? "Ứng dụng" : (modelData.is_pdf ? "PDF" : "Tệp")
                                                        textFormat: Text.PlainText
                                                        color: desk.muted
                                                        font.pixelSize: 10
                                                        font.weight: Font.Medium
                                                    }
                                                }
                                            }

                                            Label {
                                                text: modelData.display_path || modelData.path || modelData.snippet || ""
                                                textFormat: Text.PlainText
                                                color: desk.muted
                                                font.pixelSize: 11
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                ToolTip.visible: hitMouseArea.containsMouse
                                                ToolTip.text: modelData.path || ""
                                            }
                                        }
                                    }
                                }
                            }
                        }
                            }
                        }

                        // Affordance to see more if there are remaining results
                        Item {
                            visible: desk.allFinderHits.length > 3
                            Layout.fillWidth: true
                            implicitHeight: seeMoreRow.implicitHeight + 8

                            RowLayout {
                                id: seeMoreRow
                                anchors.centerIn: parent
                                spacing: 6

                                QuietButton {
                                    id: seeMoreButton
                                    objectName: "seeMoreFinderHits"
                                    text: desk.showAllFinderHits
                                        ? "Thu gọn (hiện 3 gợi ý đầu)"
                                        : ("Xem thêm " + desk.remainingFinderHits + " kết quả khác…")
                                    iconName: desk.showAllFinderHits ? "chevron-up" : "chevron-down"
                                    Accessible.name: desk.showAllFinderHits
                                        ? "Thu gọn danh sách gợi ý còn 3 mục"
                                        : ("Xem thêm " + desk.remainingFinderHits + " kết quả tìm kiếm còn lại")
                                    onClicked: {
                                        desk.showAllFinderHits = !desk.showAllFinderHits
                                        if (desk.selectedFinderIndex >= (desk.visibleFinderHits || []).length) {
                                            desk.selectedFinderIndex = -1
                                        }
                                        editor.forceActiveFocus()
                                    }
                                }
                            }
                        }

                        // Bottom Action Bar reflecting selected hit actions cleanly with tactile keycaps
                        Rectangle {
                            visible: desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            height: 1
                            color: desk.edge
                        }
                        Rectangle {
                            id: bottomActionBar
                            objectName: "bottomActionBar"
                            visible: desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
                            Layout.fillWidth: true
                            implicitHeight: finderShortcuts.implicitHeight + 10
                            radius: desk.controlRadius
                            color: "transparent"

                            readonly property var selectedHit: (desk.visibleFinderHits || [])[desk.selectedFinderIndex] || ({})

                            Flow {
                                id: finderShortcuts
                                x: 0
                                y: 4
                                width: parent.width
                                spacing: 5

                                KeycapBadge {
                                    objectName: "finderReadAction"
                                    visible: Boolean(bottomActionBar.selectedHit.is_pdf)
                                    keyText: "↵"
                                    labelText: bottomActionBar.width < 400 ? "Chọn PDF" : "Chọn PDF để đọc / hỏi"
                                    Accessible.name: "Chọn PDF để đọc hoặc hỏi Chuột, Enter"
                                    primary: true
                                    onClicked: {
                                        var idx = desk.selectedFinderIndex
                                        desk.selectedFinderIndex = -1
                                        desk.liveController.openSelectedHit(idx)
                                        editor.text = ""
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
                                                    editor.text = restored
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
                                                    editor.text = restored
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
                                                editor.text = restored
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
                                                editor.text = restored
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
                        visible: desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "apps"
                        Layout.fillWidth: true
                        QuietButton {
                            objectName: "logToggle"
                            text: "Chi tiết & nhật ký"
                            iconName: desk.logOpen ? "chevron-down" : "chevron-right"
                            iconSize: 13
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
                    Item { Layout.fillWidth: true; implicitHeight: desk.liveMode ? 32 : 8 }
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
            visible: true
            x: composer.x + 6
            y: (desk.expanded && desk.hasWorkbench) ? (composer.y + 1) : (composer.y - 5)
            width: composer.width
            height: (desk.expanded && desk.hasWorkbench) ? (composer.height - 4) : composer.height
            radius: composer.radius
            rotation: (desk.expanded && desk.hasWorkbench) ? -0.8 : -1.1
            antialiasing: true
            color: desk.backingColor
            border.width: 1
            border.color: desk.edge
            z: 0
        }
        Button {
            id: note
            objectName: "notice"
            visible: !desk.expanded && desk.hasWorkbench
            x: 126
            y: composer.y - height + (desk.hasAnswerPreview ? 12 : 7)
            width: desk.hasAnswerPreview || (desk.liveMode && desk.liveSnapshot.busy) || desk.hasFinderPreview ? Math.min(360, composer.width - x) : Math.min(228, composer.width - x)
            height: desk.hasAnswerPreview ? Math.max(76, Math.min(112, minPreviewContent.implicitHeight + topPadding + bottomPadding)) : desk.hasFinderPreview || desk.hasPagePreview || (desk.liveMode && desk.liveSnapshot.busy) ? Math.max(48, minPreviewContent.implicitHeight + topPadding + bottomPadding) : desk.noticeVisible ? 61 : 48
            rotation: -1.2
            z: 3
            Accessible.name: desk.hasFinderPreview
                ? ("Gợi ý tìm kiếm: " + (desk.allFinderHits[0].title || "") + " (" + (desk.allFinderHits[0].kind === "application" ? "Ứng dụng" : "Tệp") + ") tại " + (desk.allFinderHits[0].display_path || desk.allFinderHits[0].path || "") + ". Mở gợi ý")
                : desk.hasAnswerPreview
                    ? (desk.noticeVisible ? "Kết quả mới. " : "") + desk.previewMeta + ". " + desk.previewBody + ". Mở câu trả lời đầy đủ"
                    : desk.liveMode && desk.liveSnapshot.busy
                        ? desk.liveSnapshot.status + ". Mở tiến trình"
                        : desk.hasPagePreview
                            ? desk.pagePreviewTitle + ". " + desk.liveSnapshot.fileName + ". Mở lại nội dung trang"
                            : desk.noticeVisible
                                ? "Có kết quả mới, mở workbench"
                                : "Mở lại workbench"
            onClicked: desk.openWorkbench()
            background: Rectangle {
                radius: 12
                antialiasing: true
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
                        text: desk.hasFinderPreview
                            ? ("Gợi ý: " + (desk.allFinderHits[0].title || "Tìm kiếm"))
                            : desk.hasAnswerPreview ? desk.previewBody : desk.liveMode && desk.liveSnapshot.busy ? desk.liveSnapshot.status : desk.liveMode && desk.liveSnapshot.errorCode ? "Xem thông báo" : desk.hasPagePreview ? desk.pagePreviewTitle : desk.phase === "working" ? "Xem tiến trình" : "Xem kết quả"
                        textFormat: Text.PlainText
                        color: desk.hasAnswerPreview || desk.hasFinderPreview ? desk.ink : desk.accent
                        font.pixelSize: 13
                        font.family: desk.liveSnapshot.answerPreviewIsCode ? "Menlo" : Qt.application.font.family
                        wrapMode: desk.liveSnapshot.answerPreviewIsCode ? Text.NoWrap : Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                    DeskIcon { name: "chevron-up"; color: desk.accent; Layout.preferredWidth: 14; Layout.preferredHeight: 14; Layout.alignment: Qt.AlignTop }
                }
                RowLayout {
                    visible: desk.hasAnswerPreview || desk.hasPagePreview || desk.hasFinderPreview || desk.noticeVisible
                    Layout.fillWidth: true
                    spacing: 5
                    Rectangle { visible: desk.noticeVisible; implicitWidth: 5; implicitHeight: 5; radius: 3; color: desk.accent }
                    Label {
                        objectName: "minAnswerMetadata"
                        Layout.fillWidth: true
                        text: desk.hasFinderPreview
                            ? ((desk.allFinderHits[0].kind === "application" ? "Ứng dụng" : "Tệp") + " · " + (desk.allFinderHits[0].display_path || desk.allFinderHits[0].path || "") + " (" + desk.allFinderHits.length + " kết quả)")
                            : desk.hasAnswerPreview ? desk.previewMeta : desk.hasPagePreview ? desk.liveSnapshot.fileName : "Kết quả mới"
                        textFormat: Text.PlainText
                        font.pixelSize: 10
                        color: desk.incompletePreview || desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                        wrapMode: desk.hasPagePreview || desk.hasFinderPreview ? Text.NoWrap : Text.Wrap
                        maximumLineCount: desk.hasPagePreview || desk.hasFinderPreview ? 1 : 2
                        elide: desk.hasPagePreview || desk.hasFinderPreview ? Text.ElideMiddle : Text.ElideRight
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
            id: finderDrawerTab
            objectName: "finderDrawerTab"
            visible: desk.hasLatentFinderHits
            anchors.right: composer.right
            anchors.rightMargin: 18
            y: composer.y - height + 9
            width: drawerTabRow.implicitWidth + 20
            height: 33
            radius: 10
            color: drawerTabMouse.containsMouse ? desk.selectedSurface : desk.utilitySurface
            border.width: 1
            border.color: desk.selectedEdge
            z: 4.5
            Accessible.name: desk.allFinderHits.length + " tệp hoặc ứng dụng khớp, bấm để mở gợi ý"
            Accessible.role: Accessible.Button

            RowLayout {
                id: drawerTabRow
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.top: parent.top
                anchors.topMargin: 5
                spacing: 6
                DeskIcon {
                    name: "folder"
                    color: desk.accent
                    width: 13
                    height: 13
                }
                Label {
                    text: desk.allFinderHits.length + " tệp/app khớp · Xem"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: desk.accent
                }
                DeskIcon {
                    name: "chevron-up"
                    color: desk.accent
                    width: 11
                    height: 11
                }
            }

            MouseArea {
                id: drawerTabMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (desk.liveController) {
                        desk.liveController.openFinderSuggestions()
                        editor.forceActiveFocus()
                    }
                }
            }
        }
        Rectangle {
            id: inlineFindBar
            objectName: "inlineFindBar"
            visible: desk.liveMode && desk.inlineFindOpen && Boolean(desk.liveSnapshot.fileName)
            x: desk.expanded ? (resultPaper.x + 22) : composer.x
            y: desk.expanded ? (resultPaper.y + 46) : (composer.y - height - 8)
            width: desk.expanded ? (resultPaper.width - 44) : composer.width
            height: 36
            radius: 8
            color: desk.utilitySurface
            border.width: 1
            border.color: desk.selectedEdge
            z: 6

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                DeskIcon {
                    name: "search"
                    color: desk.accent
                    width: 13
                    height: 13
                }

                TextField {
                    id: pdfSearchField
                    objectName: "pdfSearchField"
                    Layout.fillWidth: true
                    implicitHeight: 28
                    padding: 0
                    leftPadding: 4
                    rightPadding: 4
                    font.pixelSize: 13
                    color: desk.ink
                    placeholderText: "Tìm từ khóa trong PDF…"
                    placeholderTextColor: desk.muted
                    selectionColor: desk.accent
                    selectedTextColor: desk.accentText
                    selectByMouse: true
                    Accessible.name: "Từ khóa cần tìm trong PDF"
                    background: null
                    onAccepted: desk.runPdfSearchAction()
                    Keys.onEscapePressed: {
                        desk.inlineFindOpen = false
                        editor.forceActiveFocus()
                    }
                }

                QuietButton {
                    objectName: "runPdfSearch"
                    text: "Tìm"
                    primary: true
                    implicitHeight: 24
                    topPadding: 2
                    bottomPadding: 2
                    leftPadding: 8
                    rightPadding: 8
                    font.pixelSize: 11
                    enabled: !desk.liveSnapshot.busy && pdfSearchField.text.trim().length > 0
                    onClicked: desk.runPdfSearchAction()
                }

                IconButton {
                    objectName: "closeInlineFind"
                    glyph: "close"
                    iconSize: 11
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 5
                    Accessible.name: "Đóng thanh tìm chữ"
                    onClicked: {
                        desk.inlineFindOpen = false
                        editor.forceActiveFocus()
                    }
                }
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
            border.width: pdfDropArea.containsDrag ? 1.5 : 1
            border.color: pdfDropArea.containsDrag ? desk.accent : (editor.activeFocus ? desk.selectedEdge : desk.edge)
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
                    radius: 8
                    color: desk.utilitySurface
                    border.width: 1
                    border.color: desk.edge
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
                            iconColor: desk.liveSnapshot.fileName ? desk.pdfInk : "transparent"
                            trailingIconName: ""
                            iconSize: 14
                            trailingIconSize: 0
                            elideText: true
                            font.pixelSize: 11
                            topPadding: 2
                            bottomPadding: 2
                            leftPadding: 4
                            rightPadding: 4
                            Accessible.name: "Tài liệu đang chọn: " + text + ", mở trang đang đọc"
                            enabled: Boolean(desk.liveSnapshot.fileName)
                            onClicked: { if (desk.liveController) desk.liveController.showCurrentPdfPage() }
                            ToolTip.visible: hovered
                            ToolTip.text: desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.title : ""
                        }
                        IconButton {
                            objectName: "openPdfSearch"
                            visible: Boolean(desk.liveSnapshot.fileName)
                            glyph: "search"
                            iconSize: 13
                            implicitWidth: 22
                            implicitHeight: 22
                            padding: 4
                            Accessible.name: "Tìm từ khóa trong PDF đang chọn"
                            onClicked: desk.openPdfSearch()
                            ToolTip.visible: hovered
                            ToolTip.text: "Tìm chữ trong PDF (⌘F)"
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
                            : (desk.liveSnapshot.fileName ? ("Hỏi Chuột về " + desk.liveSnapshot.fileName + "…") : "Tìm tệp, mở app hoặc hỏi Chuột…")
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
                                if (desk.liveSnapshot.view === "apps" || !desk.isAppsCommand(text)) {
                                    desk.liveController.onComposerTextChanged(text)
                                }
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
                                var hits = desk.visibleFinderHits
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
                                var hits = desk.visibleFinderHits
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
                                editor.text = restored
                                return
                            }
                            if (desk.liveMode && desk.liveSnapshot.view === "finder") {
                                event.accepted = true
                                if (desk.selectedFinderIndex >= 0) {
                                    desk.selectedFinderIndex = -1
                                } else {
                                    desk.liveController.dismissFinder()
                                }
                                return
                            }
                            event.accepted = false
                        }
                        Keys.onReturnPressed: event => desk.handleComposerReturn(event)
                        Keys.onEnterPressed: event => desk.handleComposerReturn(event)
                    }
                    }
                    QuietButton {
                        id: sendControl
                        objectName: "sendButton"
                        text: ""
                        iconName: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy) ? "stop" : (desk.liveMode && desk.liveSnapshot.view === "apps" ? "enter" : "arrow-up")
                        iconSize: 16
                        leftPadding: 0
                        rightPadding: 0
                        topPadding: 0
                        bottomPadding: 0
                        Accessible.name: desk.liveMode ? (desk.liveSnapshot.busy ? "Dừng yêu cầu" : (desk.liveSnapshot.view === "apps" ? "Mở ứng dụng đã chọn" : "Gửi câu hỏi cho Chuột")) : desk.phase === "receiving" ? "Dừng yêu cầu minh họa" : "Gửi yêu cầu minh họa"
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
                                    editor.text = restored
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
                        objectName: "uiBuildLabel"
                        visible: desk.liveMode
                        text: desk.uiBuildLabel
                        textFormat: Text.PlainText
                        color: desk.muted
                        font.pixelSize: 11
                        topPadding: 4
                        bottomPadding: 4
                        leftPadding: 0
                        rightPadding: 2
                        Accessible.name: "Bản build giao diện " + desk.uiBuildLabel
                        ToolTip.visible: dragHandle.containsMouse
                        ToolTip.text: "Bản build giao diện · Kéo để di chuyển cửa sổ"
                        MouseArea { id: dragHandle; objectName: "dragHandle"; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.OpenHandCursor; onPressed: desk.moveRequested() }
                    }
                    RowLayout {
                        visible: desk.liveMode
                        Layout.fillWidth: true
                        spacing: 5
                        Label {
                            text: "·"
                            color: desk.muted
                            opacity: 0.65
                            font.pixelSize: 11
                        }
                        Rectangle {
                            visible: !pdfDropArea.containsDrag && !desk.liveSnapshot.busy && desk.liveSnapshot.view === "none" && !desk.liveSnapshot.fileName
                            implicitWidth: 6
                            implicitHeight: 6
                            radius: 3
                            color: desk.accent
                            opacity: 0.75
                        }
                        Label {
                            objectName: "composerDropStatus"
                            Layout.fillWidth: true
                            text: pdfDropArea.containsDrag ? "Thả PDF vào bàn Chuột"
                                : (desk.liveSnapshot.busy && !desk.expanded) ? desk.liveSnapshot.status
                                : desk.liveSnapshot.view === "finder" ? "↑↓ chọn · ↵ mở · Esc đóng"
                                : (desk.liveSnapshot.view === "page" || desk.liveSnapshot.fileName) ? "↵ hỏi Chuột · ⌘F tìm chữ trong PDF"
                                : desk.liveSnapshot.view === "answer" ? (desk.hasLatentFinderHits ? "↵ hỏi tiếp Chuột · Bấm ngăn trên mở tệp" : "↵ hỏi tiếp Chuột")
                                : "Chuột sẵn sàng"
                            elide: Text.ElideRight
                            color: pdfDropArea.containsDrag ? desk.accent : desk.muted
                            font.weight: pdfDropArea.containsDrag ? Font.Medium : Font.Normal
                            font.pixelSize: 11
                        }
                    }
                    QuietButton {
                        objectName: "choosePdf"
                        visible: desk.liveMode
                        text: ""
                        iconName: "paperclip"
                        iconSize: 16
                        leftPadding: 0
                        rightPadding: 0
                        topPadding: 0
                        bottomPadding: 0
                        implicitWidth: 30
                        implicitHeight: 30
                        Accessible.name: desk.liveSnapshot.fileName ? "Đổi PDF" : "Chọn PDF"
                        ToolTip.visible: hovered
                        ToolTip.text: desk.liveSnapshot.fileName ? "Đổi hoặc kéo thả PDF khác" : "Chọn hoặc kéo thả PDF"
                        onClicked: pdfDialog.open()
                    }
                    QuietButton {
                        objectName: "closeDesk"
                        visible: desk.liveMode
                        text: ""
                        iconName: "close"
                        iconSize: 16
                        leftPadding: 0
                        rightPadding: 0
                        topPadding: 0
                        bottomPadding: 0
                        implicitWidth: 30
                        implicitHeight: 30
                        Accessible.name: "Đóng cửa sổ RAT"
                        onClicked: desk.closeRequested()
                    }
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
    Shortcut {
        sequence: "Ctrl+F"
        enabled: desk.liveMode && Boolean(desk.liveSnapshot.fileName)
        onActivated: desk.openPdfSearch()
    }
    Shortcut {
        sequence: "Meta+F"
        enabled: desk.liveMode && Boolean(desk.liveSnapshot.fileName)
        onActivated: desk.openPdfSearch()
    }
    Shortcut {
        sequences: [StandardKey.Close, StandardKey.Quit]
        enabled: desk.liveMode
        onActivated: desk.closeRequested()
    }
    Shortcut {
        sequence: "Escape"
        enabled: desk.liveMode && (desk.expanded || desk.inlineFindOpen)
        onActivated: {
            if (desk.inlineFindOpen) {
                desk.inlineFindOpen = false
                editor.forceActiveFocus()
            } else if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                editor.text = restored
                editor.forceActiveFocus()
            } else if (desk.liveSnapshot.view === "finder") {
                if (desk.selectedFinderIndex >= 0) {
                    desk.selectedFinderIndex = -1
                } else {
                    desk.liveController.dismissFinder()
                }
                editor.forceActiveFocus()
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
                editor.text = restored
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
                editor.text = restored
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
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
    Shortcut {
        sequence: "Meta+Y"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
}
