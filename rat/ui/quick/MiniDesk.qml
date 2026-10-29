import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQml.Models

Rectangle {
    id: desk
    objectName: "miniDesk"
    color: "transparent"
    property var liveController
    property var liveSnapshot: ({finderHits: [], surface: "result", busy: false})
    property url mascotSource
    property url lookHeadSource
    property url lookIdleSource
    property url lookErrorSource
    property url lookPeekSource
    property real floatingHeadSize: 144
    property real floatingHeadOpticalHeight: 112
    property real lookMascotWidth: 176
    property real lookMascotHeight: 176
    property real lookOpticalHeight: 134
    property real sharedPanelWidth: 580
    property real sharedTextSize: 16
    property string buildLabel: "source"
    property real maxCornerSpeechHeight: 300
    property real composerWidthFloor: 240
    property bool darkMode: false
    property bool reduceMotion: false
    property real maxPaperHeight: 380
    property real maxPanelHeight: 640
    property real panelX: 0
    property real panelY: 128
    property real panelWidth: 580
    property real lookPlacedHeight: 300
    property bool mascotOnRight: false
    property real ratX: 6
    property real ratY: 0
    property bool animatePlacement: false
    property bool showAllFinderHits: false
    property int selectedFinderIndex: -1
    property string keyboardOwner: "composer"
    property bool syncingDraft: false
    property bool restoringScroll: false
    property bool showAdvancedSettings: false
    property bool showDiagnostics: false
    property bool showTranslationDetails: false
    property string folderPurpose: "settings"
    property string settingsError: ""
    property string setupError: ""
    property var expandedGroups: ({})
    readonly property string surface: liveSnapshot.surface || "result"
    readonly property bool compact: liveSnapshot.interactionExtent !== "expanded"
    readonly property bool composing: Boolean(liveSnapshot.composerVisible)
    readonly property bool auxiliary: surface === "welcome" || surface === "help" || surface === "settings"
    readonly property bool lookActive: compact && !auxiliary && surface === "result"
    readonly property bool floatingHead: true
    readonly property bool previewing: !auxiliary && Boolean(liveSnapshot.pendingPreviewOpen)
    readonly property bool noticeVisible: !auxiliary && Boolean(liveSnapshot.selectionNotice)
    readonly property bool taskVisible: !previewing && !noticeVisible
    readonly property bool simpleAnswer: compact && !auxiliary && surface === "result" && taskVisible
        && !liveSnapshot.busy && liveSnapshot.phase === "result"
        && (liveSnapshot.view === "translation" || liveSnapshot.view === "analysis")
    property real heldReaderHeight: 0
    readonly property real panelBudget: compact && !auxiliary ? ((composing || noticeVisible || previewing) ? maxCornerSpeechHeight : Math.min(160, maxCornerSpeechHeight)) : maxPanelHeight
    readonly property bool paperVisible: !liveSnapshot.bubbleCollapsed && Boolean(liveSnapshot.hasWorkbench || previewing || noticeVisible)
    readonly property bool bodyVisible: auxiliary || paperVisible
    readonly property bool ocrDirty: Boolean(liveSnapshot.ocrDirty)
    readonly property bool ocrPanelVisible: surface === "ocr"
    readonly property string draftText: editor.text
    readonly property var allFinderHits: liveSnapshot.finderHits || []
    readonly property var visibleFinderHits: showAllFinderHits ? allFinderHits : allFinderHits.slice(0, 5)
    // Only transient native input/menu ownership exempts outside dismissal.
    readonly property bool focusOwned: imageDialog.visible || folderDialog.visible || Boolean(targetLanguage.popup && targetLanguage.popup.visible) || Boolean(sourceLanguage.popup && sourceLanguage.popup.visible) || Boolean(backend.popup && backend.popup.visible) || Boolean(cloudProvider.popup && cloudProvider.popup.visible) || moreMenu.visible || historyMenu.visible || analysisMenu.visible || diagnosticDialog.visible || Boolean(shortcutChord.popup && shortcutChord.popup.visible) || editorMenu.visible || readerMenu.visible || Boolean(liveSnapshot.dropActive)
    readonly property bool imageDropEnabled: !auxiliary && !imageDialog.visible && !folderDialog.visible
    readonly property bool layoutExpanded: !compact
    readonly property real preferredPanelHeight: panel.height
    readonly property real preferredPanelWidth: compact && !auxiliary ? Math.min(320, composerWidthFloor) : (liveSnapshot.sourceVisible || surface === "workbench") ? 900 : sharedPanelWidth
    readonly property bool lookEngaged: panelHover.hovered || headMouse.containsMouse || resultScroll.moving || editor.activeFocus || translationArea.activeFocus || Boolean(translationArea.selectedText) || noticeReader.activeFocus || Boolean(noticeReader.selectedText) || readerMenu.visible
    readonly property rect cornerInkBounds: headPose.visualBounds
    readonly property point cornerMouth: headPose.speechAnchor
    readonly property rect panelRect: !panel.visible ? Qt.rect(0,0,0,0) : Qt.rect(panel.x + panelSkin.occupiedRect.x, panel.y + panelSkin.occupiedRect.y, panelSkin.occupiedRect.width, panelSkin.occupiedRect.height)
    readonly property rect mascotRect: Qt.rect(mascotItem.x, mascotItem.y, mascotItem.width, mascotItem.height)
    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color backingColor: darkMode ? "#3a4332" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
    readonly property color pdfInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property int cardRadius: 10
    readonly property int controlRadius: 10
    readonly property bool failed: liveSnapshot.phase === "error" || liveSnapshot.phase === "cancelled"
    readonly property bool recoveryVisible: failed || (liveSnapshot.phase === "partial" && (liveSnapshot.view !== "finder" || allFinderHits.length === 0))
    readonly property string recoveryAction: liveSnapshot.organizationRecoverySuggested ? "journal" : liveSnapshot.imageInputSuggested ? "image" : (liveSnapshot.finderSettingsSuggested || liveSnapshot.translationSettingsSuggested) ? "settings" : liveSnapshot.canRetryRequest ? "retry" : ""
    readonly property string title: surface === "welcome" ? "Xin chào, mình là RAT" : surface === "help" ? "Thiết lập & trợ giúp" : surface === "settings" ? "Cài đặt" : surface === "ocr" ? "Sửa chữ trong ảnh" : surface === "image" ? "Ảnh nguồn" : surface === "workbench" ? "Workbench" : surface === "source" ? "Chữ nhận ban đầu" : !paperVisible ? "RAT" : liveSnapshot.view === "finder" ? "File tìm được" : liveSnapshot.view === "organization" ? "Sắp xếp thư mục" : liveSnapshot.view === "translation" ? "Bản dịch" : liveSnapshot.view === "analysis" ? liveSnapshot.status : "Yêu cầu của bạn"
    signal moveRequested()
    signal hideRequested()

    Component.onCompleted: {
        liveSnapshot = liveController.snapshot
        editor.text = liveSnapshot.draftText || ""
    }
    function saveScroll() { if (taskVisible && !auxiliary) liveController.rememberScroll(resultScroll.contentY) }
    function navigate(next) { saveScroll(); liveController.showSurface(next); if (next !== "image") Qt.callLater(focusComposer) }
    function goBack() { saveScroll(); liveController.backSurface(); Qt.callLater(function() { if (!desk.lookActive) focusComposer(); else restoreReader() }) }
    function restoreReader() {
        var saved = liveController.snapshot
        if (taskVisible && !auxiliary) {
            resultScroll.contentY = Math.max(0, Math.min(saved.scrollOffset || 0,
                Math.max(0, resultScroll.contentHeight - resultScroll.height)))
            if (surface === "result" && translationArea.visible) {
                if (saved.readerAnchorText === translationArea.text && translationArea.text.length > 0) {
                    var origin = translationArea.mapToItem(resultScroll.contentItem, 0, 0).y
                    var rect = translationArea.positionToRectangle(Math.min(saved.readerAnchorPosition, translationArea.length))
                    resultScroll.contentY = Math.max(0, Math.min(origin + rect.y + saved.readerAnchorDelta,
                        Math.max(0, resultScroll.contentHeight - resultScroll.height)))
                }
                translationArea.select(saved.lookSelectionStart || 0, saved.lookSelectionEnd || 0)
            }
        } else if (!auxiliary) resultScroll.contentY = 0
        restoringScroll = false
    }
    onPanelWidthChanged: { restoringScroll = true; Qt.callLater(restoreReader) }
    function growComposerWidth() {
        if (compact && !auxiliary)
            composerWidthFloor = Math.max(composerWidthFloor, composerMeasure.advanceWidth > 150 ? 320 : 240)
    }
    function beginCornerPresentation() {
        // A fresh invocation may choose a smaller tier; typing/clearing during
        // the invocation only grows it, avoiding a collapse when Send clears it.
        heldReaderHeight = 0
        if (compact)
            composerWidthFloor = composerMeasure.advanceWidth > 150 ? 320 : 240
    }
    function focusComposer() {
        if (composing && !auxiliary && surface === "result") editor.forceActiveFocus()
        else if (surface === "ocr" && paperVisible) ocrEditor.forceActiveFocus()
        else if (surface === "settings") targetLanguage.forceActiveFocus()
        else if (auxiliary) setupPrimary.forceActiveFocus()
        else if (keyboardOwner === "files" && paperVisible && liveSnapshot.view === "finder") fileResults.forceActiveFocus()
        else if (!composing && paperVisible) {
            if (surface === "result" && liveSnapshot.view === "finder") fileResults.forceActiveFocus()
            else if (surface === "result" && translationArea.visible) translationArea.forceActiveFocus()
            else resultScroll.forceActiveFocus()
        }
        else if (composing) editor.forceActiveFocus()
    }
    function dismissTransient() { moreMenu.close(); historyMenu.close(); analysisMenu.close(); readerMenu.close(); editorMenu.close(); diagnosticDialog.close(); providerKey.clear() }
    function pasteDraft() {
        var input = liveController.pasteInput(editor.text)
        if (input.kind !== "image" && input.text) {
            var start = editor.selectionStart
            if (editor.selectionStart !== editor.selectionEnd) editor.remove(start, editor.selectionEnd)
            editor.insert(start, input.text)
            editor.cursorPosition = start + input.text.length
            liveController.rememberPaste(editor.text, input.kind)
        }
        if (!auxiliary) editor.forceActiveFocus()
    }
    function openSettings() {
        if (surface !== "settings") {
            var p = liveController.preferences
            folderList.model = p.roots.slice()
            sourceLanguage.currentIndex = Math.max(0, sourceLanguage.indexOfValue(p.source_language))
            targetLanguage.currentIndex = Math.max(0, targetLanguage.indexOfValue(p.target_language))
            llmEnabled.checked = p.llm_enabled === true
            backend.currentIndex = Math.max(0, backend.indexOfValue(p.translation_provider))
            cloudProvider.currentIndex = Math.max(0, cloudProvider.indexOfValue(p.provider))
            cloudModel.text = p.model
            shortcutChord.currentIndex = Math.max(0, shortcutChord.indexOfValue(p.hotkey_chord || "option_shift_space"))
            freeFallback.checked = p.free_fallback
            providerKey.clear(); settingsError = ""; showAdvancedSettings = false
        }
        navigate("settings")
    }
    function editPreviousRequest() { liveController.editRequest(); editor.forceActiveFocus(); editor.cursorPosition = editor.length }
    function toggleGroup(name) {
        var groups = Object.assign({}, expandedGroups)
        groups[name] = !groups[name]; expandedGroups = groups
    }
    function recover() {
        if (recoveryAction === "journal") liveController.recoverOrganization()
        else if (recoveryAction === "image") imageDialog.open()
        else if (recoveryAction === "settings") openSettings()
        else if (recoveryAction === "retry") liveController.retryRequest()
    }
    function selectFile(index) {
        if (!visibleFinderHits.length) return
        selectedFinderIndex = Math.max(0, Math.min(index, visibleFinderHits.length - 1))
        keyboardOwner = "files"; fileResults.forceActiveFocus()
        Qt.callLater(function() {
            var row = fileRows.itemAt(selectedFinderIndex)
            if (!row) return
            var y = row.mapToItem(bodyColumn, 0, 0).y
            if (y < resultScroll.contentY) resultScroll.contentY = y
            else if (y + row.height > resultScroll.contentY + resultScroll.height) resultScroll.contentY = y + row.height - resultScroll.height
        })
    }
    Connections {
        target: liveController
        function onChanged() {
            var next = liveController.snapshot
            if (next.busy && !desk.liveSnapshot.busy)
                desk.heldReaderHeight = Math.max(140, resultSheet.visible ? resultSheet.height : 0)
            var moved = next.surface !== desk.surface || next.taskId !== desk.liveSnapshot.taskId || next.interactionExtent !== desk.liveSnapshot.interactionExtent || next.lookSurface !== desk.liveSnapshot.lookSurface || Boolean(next.selectionNotice) !== desk.noticeVisible
            if (moved) desk.restoringScroll = true
            if (next.taskId !== desk.liveSnapshot.taskId) {
                desk.selectedFinderIndex = -1; desk.showAllFinderHits = false
                desk.expandedGroups = ({}); desk.showTranslationDetails = false
            }
            if (desk.surface === "settings" && next.surface !== "settings") providerKey.clear()
            desk.liveSnapshot = next
            if (editor.text !== next.draftText) {
                desk.syncingDraft = true; editor.text = next.draftText || ""; desk.syncingDraft = false
            }
            if (moved) Qt.callLater(function() {
                resultScroll.contentY = Math.max(0, Math.min(desk.liveSnapshot.scrollOffset || 0, resultScroll.contentHeight-resultScroll.height))
                desk.restoringScroll = false
                desk.restoreReader()
            })
        }
        function onSettingsRequested() { desk.openSettings(); desk.showAdvancedSettings = Boolean(desk.liveSnapshot.translationSettingsSuggested) }
        function onHelpRequested() { desk.navigate("help") }
    }

    // One mounted task panel and editor at every extent; resizing changes constraints only.
    Item {
        id: panel
        visible: height > 0
        x: desk.panelX; y: desk.panelY
        width: Math.max(1, desk.panelWidth)
        height: desk.auxiliary ? resultSheet.height : (desk.composing ? composer.height : 0) + (desk.bodyVisible ? resultSheet.height : 0)
        HoverHandler { id: panelHover }
        SpeechSurface {
            id: panelSkin
            anchors.fill: parent
            cornerRadius: 14; padding: 12
            paperColor: desk.paperColor; edgeColor: desk.edge
            anchorPoint: Qt.point(desk.ratX + headPose.speechAnchor.x - panel.x, desk.ratY + headPose.speechAnchor.y - panel.y)
        }
        Rectangle {
            id: resultSheet
            visible: desk.bodyVisible
            x: 0
            width: parent.width
            height: visible ? Math.max(1, Math.min(desk.panelBudget - (desk.auxiliary || !desk.composing ? 0 : composer.height), desk.noticeVisible || desk.previewing ? Math.max(200, paperColumn.implicitHeight + 24) : desk.heldReaderHeight > 0 && desk.compact && !desk.auxiliary && !desk.simpleAnswer ? Math.max(140, desk.heldReaderHeight) : paperColumn.implicitHeight + 24)) : 0
            radius: 14; color: "transparent"; border.color: "transparent"
            QuietButton {
                visible: desk.simpleAnswer && !desk.composing
                x: parent.width - width - 3; y: 2; z: 3
                iconName: "close"; iconSize: 12; implicitWidth: 22; implicitHeight: 22
                Accessible.name: "Đóng kết quả"; onClicked: desk.liveController.collapseBubble()
            }
            Rectangle {
                id: fullSource
                visible: desk.taskVisible && Boolean(desk.liveSnapshot.sourceVisible) && !desk.auxiliary && parent.width >= 700
                x: 22; y: 14; width: Math.min(260, parent.width * 0.32)
                height: parent.height - 50; radius: 10; color: desk.utilitySurface
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 10; spacing: 8
                    Label { text: "Nguồn đang dùng" + (desk.liveSnapshot.captureSourceApp ? " · " + desk.liveSnapshot.captureSourceApp : ""); textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap; color: desk.muted; font.pixelSize: 11 }
                    Image {
                        visible: Boolean(desk.liveSnapshot.imagePreviewUrl)
                        source: desk.liveSnapshot.imagePreviewUrl || ""; fillMode: Image.PreserveAspectFit
                        Layout.fillWidth: true; Layout.preferredHeight: 120
                        MouseArea { anchors.fill: parent; onClicked: desk.navigate("image") }
                    }
                    ScrollView {
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                        TextArea {
                            text: desk.liveSnapshot.ocrText || desk.liveSnapshot.requestText || ""
                            textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: true
                            wrapMode: TextEdit.Wrap; color: desk.ink; font.pixelSize: 12; background: null
                        }
                    }
                }
            }
            ColumnLayout {
                id: paperColumn
                x: fullSource.visible ? fullSource.width + 24 : 12
                y: 12; width: parent.width - x - 12
                height: Math.max(1, parent.height - 24); spacing: 8
                RowLayout {
                    visible: !desk.simpleAnswer
                    Layout.fillWidth: true; spacing: 6
                    QuietButton { visible: desk.auxiliary || (desk.paperVisible && desk.surface !== "result"); iconName: "arrow-left"; implicitWidth: 30; Accessible.name: "Quay lại"; onClicked: desk.goBack() }
                    Label { text: (desk.liveSnapshot.pinned ? "● " : "") + (desk.previewing ? "Đoạn Clipboard · Chưa dịch" : desk.noticeVisible ? "Quick Look" : desk.title); textFormat: Text.PlainText; color: desk.ink; font.pixelSize: 11; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                    BusyIndicator { running: Boolean(desk.liveSnapshot.busy); visible: running; implicitWidth: 18; implicitHeight: 18 }
                    QuietButton { visible: desk.auxiliary || !desk.composing; iconName: "close"; implicitWidth: 28; Accessible.name: "Ẩn RAT"; onClicked: desk.hideRequested() }
                    QuietButton { visible: Boolean(desk.liveSnapshot.busy) && !desk.auxiliary; iconName: "stop"; implicitWidth: 28; Accessible.name: "Dừng yêu cầu"; onClicked: desk.liveController.cancel() }
                    QuietButton { visible: desk.paperVisible && !desk.auxiliary && !desk.compact && desk.taskVisible; text: "Nguồn"; onClicked: desk.liveController.toggleSource() }
                    QuietButton { visible: desk.paperVisible && !desk.auxiliary; iconName: desk.compact ? "chevron-up" : "chevron-down"; implicitWidth: 28; Accessible.name: desk.compact ? "Mở rộng" : "Thu gọn"; onClicked: { desk.saveScroll(); desk.liveController.setExpanded(desk.compact) } }
                }
                RowLayout {
                    visible: desk.paperVisible && !desk.auxiliary && !desk.compact && desk.taskVisible && Boolean(desk.liveSnapshot.requestText)
                    Layout.fillWidth: true
                    Image {
                        visible: Boolean(desk.liveSnapshot.imagePreviewUrl)
                        source: desk.liveSnapshot.imagePreviewUrl || ""; fillMode: Image.PreserveAspectFit; cache: false
                        Layout.preferredWidth: 42; Layout.preferredHeight: 32
                        Accessible.name: "Xem ảnh nguồn"
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: desk.navigate("image") }
                    }
                    Label { text: desk.liveSnapshot.requestText || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight; ToolTip.visible: requestHover.containsMouse; ToolTip.text: text; MouseArea { id: requestHover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton } }
                    QuietButton { text: "Sửa"; enabled: !desk.liveSnapshot.busy; Accessible.name: "Sửa yêu cầu đã gửi"; onClicked: desk.editPreviousRequest() }
                }
                Label {
                    objectName: "resultStatus"
                    maximumLineCount: desk.compact ? 2 : 2147483647
                    elide: Text.ElideRight
                    visible: !desk.simpleAnswer && desk.paperVisible && !desk.auxiliary && desk.taskVisible && Boolean(desk.liveSnapshot.status)
                    text: desk.liveSnapshot.status || ""; textFormat: Text.PlainText
                    color: desk.liveSnapshot.error ? desk.pdfInk : desk.muted; font.pixelSize: 12
                    wrapMode: Text.Wrap; Layout.fillWidth: true
                }
                Flickable {
                    id: resultScroll
                    objectName: "resultPaper"
                    visible: desk.bodyVisible
                    Layout.fillWidth: true
                    Layout.fillHeight: true; Layout.minimumHeight: 0
                    Layout.preferredHeight: Math.min(desk.maxPaperHeight, bodyColumn.implicitHeight)
                    contentWidth: width; contentHeight: bodyColumn.implicitHeight; clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {
                        policy: resultScroll.contentHeight > resultScroll.height + 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    }
                    onContentYChanged: {
                        if (!desk.restoringScroll && visible && desk.taskVisible && !desk.auxiliary) {
                            desk.liveController.rememberScroll(contentY)
                            if (translationArea.visible && desk.surface === "result") {
                                var origin = translationArea.mapToItem(resultScroll.contentItem, 0, 0).y
                                var y = contentY - origin
                                if (y >= 0 && y <= translationArea.height) {
                                    var pos = translationArea.positionAt(0, y)
                                    desk.liveController.rememberReadingAnchor(translationArea.text, pos,
                                        y - translationArea.positionToRectangle(pos).y)
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        id: bodyColumn
                        width: Math.max(1, resultScroll.width - 8); spacing: 12
                        GridLayout {
                            visible: desk.surface === "workbench"; Layout.fillWidth: true; columns: width >= 700 ? 3 : 1; columnSpacing: 12; rowSpacing: 16
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 6
                                Label { text: "Trao đổi"; font.weight: Font.DemiBold; color: desk.ink }
                                Repeater { model: desk.liveSnapshot.publicTurns || []
                                    delegate: Label { required property var modelData; text: modelData.role + ": " + modelData.text
                                        textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.ink; Layout.fillWidth: true }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 6
                                Label { text: "Tiến trình"; font.weight: Font.DemiBold; color: desk.ink }
                                Repeater { model: desk.liveSnapshot.publicSteps || []
                                    delegate: Label { required property var modelData; text: modelData.operation + " · " + modelData.status + (modelData.checks ? " · " + modelData.checks : "")
                                        textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; Layout.fillWidth: true }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 6
                                Label { text: "Nguồn & kết quả"; font.weight: Font.DemiBold; color: desk.ink }
                                Label { text: desk.liveSnapshot.hasOcrSource ? (desk.liveSnapshot.ocrText || "") : "Chưa có đoạn nguồn được giữ."
                                    textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; Layout.fillWidth: true }
                                Label { text: desk.liveSnapshot.text || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.ink; Layout.fillWidth: true }
                            }
                        }
                        TextArea {
                            id: noticeReader
                            visible: desk.previewing || desk.noticeVisible
                            text: desk.noticeVisible ? desk.liveSnapshot.selectionNotice : desk.liveSnapshot.pendingPreviewText || ""
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText
                            background: null; color: desk.ink; font.pixelSize: desk.sharedTextSize; padding: 0; Layout.fillWidth: true
                            Keys.onPressed: event => { if (event.matches(StandardKey.Copy) && selectedText.length > 0) { event.accepted = true; desk.liveController.copyLookSelection(selectedText) } }
                            MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton; onClicked: { readerMenu.sourceEditor = noticeReader; readerMenu.popup() } }
                        }
                        ColumnLayout {
                            visible: desk.taskVisible; Layout.fillWidth: true; spacing: 12
                        ColumnLayout {
                            visible: !desk.auxiliary && desk.surface === "result" && Boolean(desk.liveSnapshot.sourceVisible) && !fullSource.visible
                            Layout.fillWidth: true
                            Label { text: "Nguồn đang dùng"; color: desk.muted; font.pixelSize: 12 }
                            TextArea {
                                text: desk.liveSnapshot.ocrText || desk.liveSnapshot.requestText || ""
                                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                                textFormat: TextEdit.PlainText; background: null
                                color: desk.ink; font.pixelSize: desk.sharedTextSize; Layout.fillWidth: true
                            }
                        }
                        TextArea {
                            visible: desk.surface === "result" && desk.liveSnapshot.view !== "notice" && Boolean(desk.liveSnapshot.agentSummary || desk.liveSnapshot.agentIncomplete)
                            text: (desk.liveSnapshot.agentIncomplete ? "Chưa hoàn tất toàn bộ yêu cầu.\n" : "") + (desk.liveSnapshot.agentSummary || ""); textFormat: TextEdit.PlainText
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: desk.ink; font.pixelSize: 14; padding: 0; background: null; Layout.fillWidth: true
                        }
                        ColumnLayout {
                            visible: desk.surface === "welcome"; Layout.fillWidth: true; spacing: 12
                            Label { text: "Chào bạn, mình là Chuột!"; color: desk.ink; font.pixelSize: 21; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { text: "Để bôi đen chữ rồi gọi Chuột, hãy cho đúng bản RAT này quyền Trợ năng."; color: desk.ink; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { text: desk.liveSnapshot.readinessBusy ? "Đang kiểm tra…" : desk.liveSnapshot.accessibilityReady ? "✓ Bản RAT này đã có quyền Trợ năng" : "1. Bấm Mở Trợ năng.\n2. Bấm + và chọn bản RAT này.\n3. Bật công tắc, quay lại và bấm Kiểm tra lại.\nNếu RAT Mini đã bật mà vẫn chưa có quyền: chọn mục RAT Mini cũ, bấm −, rồi thêm đúng bản này bằng +."; color: desk.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            RowLayout {
                                Layout.fillWidth: true
                                QuietButton { text: "Mở Trợ năng"; onClicked: desk.liveController.openSelectionAccess() }
                                QuietButton { text: "Hiện bản RAT"; onClicked: desk.liveController.revealRunningApp() }
                                QuietButton { text: "Kiểm tra lại"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.checkReadiness(false) }
                            }
                            Label { visible: Boolean(desk.liveSnapshot.runningBundlePath); text: desk.liveSnapshot.runningBundlePath || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 11; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                            Label { text: "Ghi màn hình chỉ cần khi bạn chọn vùng chữ. RAT sẽ hỏi khi bạn dùng chức năng đó."; color: desk.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
                            Label { text: desk.liveSnapshot.readinessStatus || ""; color: desk.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
                            QuietButton { text: "Xem thiết lập & trợ giúp"; onClicked: desk.navigate("help") }
                        }
                        ColumnLayout {
                            visible: desk.surface === "help"; Layout.fillWidth: true; spacing: 12
                            Label { text: "Bạn có thể bắt đầu ngay. Khi cần, RAT sẽ hướng dẫn riêng cho chức năng chưa sẵn sàng."; color: desk.ink; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Repeater {
                                model: desk.liveSnapshot.readinessSummary || []
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true; spacing: 3
                                    Label { text: modelData.label + " · " + (modelData.state === "action_required" ? "Cần xử lý" : modelData.state === "ready" ? "Có thành phần" : "Chưa kiểm chứng"); textFormat: Text.PlainText; color: modelData.state === "action_required" ? desk.pdfInk : desk.ink; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                    Label { text: modelData.detail; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                }
                            }
                            Label { text: desk.liveSnapshot.readinessStatus || "Chưa chạy kiểm tra trên máy này."; color: desk.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                            Label { text: "Thả ảnh và dán ảnh không cần cấp Ghi màn hình hay Trợ năng cho RAT. Chọn thư mục trong Cài đặt để tìm hoặc sắp xếp file."; color: desk.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                            Label { text: "Quick Look · " + desk.liveSnapshot.shortcutLabel + (desk.liveSnapshot.hotkeyStatus ? " · Chưa kết nối" : ""); color: desk.ink; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Repeater {
                                model: desk.liveSnapshot.diagnosticEvents || []
                                delegate: Label { required property var modelData; text: modelData.sequence + " · " + modelData.label; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            }
                            QuietButton { text: "Xuất chẩn đoán…"; onClicked: diagnosticDialog.open() }
                            Label { visible: Boolean(desk.liveSnapshot.settingsNotice); text: desk.liveSnapshot.settingsNotice || ""; textFormat: Text.PlainText; color: desk.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            QuietButton { text: desk.showDiagnostics ? "Ẩn chi tiết kỹ thuật" : "Chi tiết kỹ thuật"; onClicked: desk.showDiagnostics = !desk.showDiagnostics }
                            ColumnLayout {
                                visible: desk.showDiagnostics; Layout.fillWidth: true; spacing: 10
                                Repeater {
                                    model: desk.liveSnapshot.readiness || []
                                    delegate: Label { required property var modelData; text: modelData.label + " — " + modelData.detail; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                }
                            }
                        }
                        ColumnLayout {
                            visible: desk.surface === "settings"; Layout.fillWidth: true; spacing: 10
                            Label {
                                visible: desk.liveSnapshot.translationSettingsSuggested
                                text: desk.liveSnapshot.status || "Kiểm tra dịch vụ dịch."
                                textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap
                                color: desk.ink; font.pixelSize: 14
                            }
                            QuietButton {
                                visible: desk.liveSnapshot.translationSettingsSuggested &&
                                    ((sourceLanguage.currentValue === "en" && targetLanguage.currentValue === "vi") ||
                                     (sourceLanguage.currentValue === "vi" && targetLanguage.currentValue === "en"))
                                text: "Chọn dịch trên máy · Anh ↔ Việt"
                                onClicked: { backend.currentIndex = backend.indexOfValue("automatic"); freeFallback.checked = false }
                            }
                            Label { text: "Quick Look · " + desk.liveSnapshot.shortcutLabel; color: desk.ink }
                            ComboBox {
                                id: shortcutChord; Layout.fillWidth: true; textRole: "label"; valueRole: "value"
                                model: [{label:"⌥⇧Space",value:"option_shift_space"},{label:"⌥⇧R",value:"option_shift_r"},{label:"⌥⇧K",value:"option_shift_k"},{label:"⌥⇧J",value:"option_shift_j"},{label:"⌃⌥Space · có thể đổi bộ gõ",value:"control_option_space"},{label:"⌃⇧Space",value:"control_shift_space"}]
                                Accessible.name: "Phím tắt Quick Look"
                            }
                            QuietButton { text: "Dùng phím này"; enabled: !desk.liveSnapshot.busy; onClicked: { desk.settingsError=desk.liveController.changeShortcut(shortcutChord.currentValue) } }
                            Label { text: "Dịch sang"; color: desk.ink; font.weight: Font.Medium }
                            ComboBox {
                                id: targetLanguage; Layout.fillWidth: true; textRole: "label"; valueRole: "value"
                                model: [{label:"Tiếng Việt",value:"vi"},{label:"English",value:"en"},{label:"日本語",value:"ja"},{label:"한국어",value:"ko"},{label:"中文",value:"zh"},{label:"Français",value:"fr"},{label:"Deutsch",value:"de"}]
                            }
                            Label { text: "Thư mục được chọn"; color: desk.ink; font.weight: Font.Medium }
                            Repeater {
                                id: folderList
                                model: []
                                delegate: RowLayout {
                                    required property string modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Label { text: modelData; textFormat: Text.PlainText; color: desk.muted; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    QuietButton { text: "Bỏ"; onClicked: { var roots=folderList.model.slice(); roots.splice(index,1); folderList.model=roots } }
                                }
                            }
                            QuietButton { text: "Thêm thư mục…"; iconName: "folder"; onClicked: { desk.folderPurpose="settings"; folderDialog.open() } }
                            Label { text: backend.currentValue === "automatic" ? "Anh ↔ Việt dịch trên máy. Ngôn ngữ khác cần mạng và gửi đoạn cần dịch đến dịch vụ online." : "Dịch vụ online đã chọn sẽ nhận nội dung bạn yêu cầu dịch."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            QuietButton { text: desk.showAdvancedSettings ? "Thu gọn nâng cao" : "Nâng cao…"; onClicked: desk.showAdvancedSettings = !desk.showAdvancedSettings }
                            ColumnLayout {
                                visible: desk.showAdvancedSettings; Layout.fillWidth: true; spacing: 10
                                Label { text: "Ngôn ngữ nguồn"; color: desk.ink }
                                ComboBox { id: sourceLanguage; Layout.fillWidth: true; textRole: "label"; valueRole: "value"; model: [{label:"Tự nhận diện",value:"auto"},{label:"English",value:"en"},{label:"Tiếng Việt",value:"vi"},{label:"日本語",value:"ja"},{label:"한국어",value:"ko"},{label:"中文",value:"zh"},{label:"Français",value:"fr"},{label:"Deutsch",value:"de"}] }
                                CheckBox { id: llmEnabled; text: "Bật suy luận cloud (tùy chọn, cần API key)" }
                                Label { text: "Tìm file, OCR và dịch Anh ↔ Việt dùng được khi tùy chọn này tắt. Bật để gửi yêu cầu nhiều bước tới dịch vụ cloud đã chọn."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                Label { text: "Dịch vụ dịch"; color: desk.ink }
                                ComboBox { id: backend; Layout.fillWidth: true; textRole: "label"; valueRole: "value"; model: [{label:"Tự động · Anh ↔ Việt trên máy",value:"automatic"},{label:"Google Translate online",value:"google_gtx"},{label:"MyMemory",value:"mymemory"},{label:"DeepL · dùng API key",value:"deepl"},{label:"Google Cloud · dùng API key",value:"google"}].concat(llmEnabled.checked ? [{label:"LLM · dùng API key",value:"llm"}] : []) }
                                Label { visible: cloudProvider.visible; text: "Dịch vụ LLM"; color: desk.ink }
                                ComboBox { id: cloudProvider; visible: llmEnabled.checked; Layout.fillWidth: true; textRole: "label"; valueRole: "value"; model: [{label:"OpenAI",value:"openai"},{label:"DeepSeek",value:"deepseek"},{label:"Groq",value:"groq"}] }
                                TextField { id: cloudModel; visible: cloudProvider.visible; Layout.fillWidth: true; placeholderText: "Tên model"; maximumLength: 128; Accessible.name: "Tên model LLM" }
                                TextField { id: providerKey; visible: llmEnabled.checked || ["deepl","google"].indexOf(backend.currentValue) >= 0; Layout.fillWidth: true; echoMode: TextInput.Password; selectByMouse: true; placeholderText: ["deepl","google"].indexOf(backend.currentValue) >= 0 ? "API key dịch · để trống để giữ key" : "API key suy luận cloud · để trống để giữ key"; Accessible.name: "API key, lưu trong Keychain" }
                                Label { visible: providerKey.visible; text: "Key lưu riêng trong Keychain của Mac. Phí và hạn mức theo tài khoản dịch vụ."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                CheckBox { id: freeFallback; text: "Cho phép MyMemory dự phòng" }
                            }
                        }
                        Image {
                            visible: desk.surface === "image"; Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(900, width * sourceSize.height / Math.max(1, sourceSize.width))
                            source: visible && desk.liveSnapshot.imagePreviewUrl ? desk.liveSnapshot.imagePreviewUrl + "/full" : ""
                            fillMode: Image.PreserveAspectFit; cache: false; Accessible.name: "Ảnh nguồn để đối chiếu chữ"
                        }
                        TextArea {
                            id: ocrEditor; objectName: "ocrSourceEditor"
                            visible: desk.surface === "ocr"; Layout.fillWidth: true; Layout.minimumHeight: 180
                            text: desk.liveSnapshot.ocrText || ""; textFormat: TextEdit.PlainText
                            readOnly: Boolean(desk.liveSnapshot.busy); selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: desk.ink; font.pixelSize: 15; padding: 10
                            background: Rectangle { color: desk.utilitySurface; radius: 8; border.color: ocrEditor.activeFocus ? desk.accent : desk.edge }
                            onTextChanged: { if (activeFocus) desk.liveController.setOcrDraft(text) }
                            Accessible.name: "Chữ trong ảnh, có thể sửa"
                        }
                        TextArea {
                            visible: desk.surface === "source"; Layout.fillWidth: true
                            text: desk.liveSnapshot.ocrOriginalText || ""; textFormat: TextEdit.PlainText
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: desk.ink; font.pixelSize: 15; padding: 0; background: null
                            Accessible.name: "Chữ nhận ban đầu, giữ nguyên"
                        }
                        Label { visible: desk.surface === "ocr" && desk.ocrDirty; text: "Chữ đã sửa chưa được dịch lại. Bản dịch trước vẫn được giữ."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        ColumnLayout {
                            visible: desk.surface === "result" && (desk.liveSnapshot.view === "translation" || desk.liveSnapshot.view === "analysis"); Layout.fillWidth: true; spacing: 8
                            TextArea { id: translationArea; objectName: "translationText";
                                TapHandler { onTapped: desk.liveController.focusLook() }
                                MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton; onClicked: { readerMenu.sourceEditor = translationArea; readerMenu.popup() } }

                                onSelectedTextChanged: { if (!desk.restoringScroll && visible) desk.liveController.rememberLookSelection(selectionStart, selectionEnd) }
                                Keys.onPressed: event => { if (event.matches(StandardKey.Copy) && selectedText.length > 0) { event.accepted = true; desk.liveController.copyLookSelection(selectedText) } }
                                 text: desk.liveSnapshot.text || ""; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: desk.ink; font.pixelSize: 16; padding: 0; rightPadding: desk.simpleAnswer ? 18 : 0; background: null; Layout.fillWidth: true; Accessible.name: "Bản dịch" }
                            Label { visible: desk.ocrDirty; text: "Kết quả này chưa dùng các chỉnh sửa chữ mới nhất."; color: desk.pdfInk; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { visible: !desk.simpleAnswer; text: desk.liveSnapshot.meta || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { visible: !desk.simpleAnswer && Boolean(desk.liveSnapshot.translationNotice); text: desk.liveSnapshot.translationNotice || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            QuietButton { visible: !desk.compact; text: desk.showTranslationDetails ? "Ẩn chi tiết" : "Chi tiết"; onClicked: desk.showTranslationDetails = !desk.showTranslationDetails }
                            Label { visible: !desk.compact && desk.showTranslationDetails; text: desk.liveSnapshot.translationDetails || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        }
                        TextArea {
                            visible: desk.surface === "result" && desk.liveSnapshot.view === "notice" && Boolean(desk.liveSnapshot.text)
                            text: desk.liveSnapshot.text || ""; textFormat: TextEdit.PlainText
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: desk.ink; font.pixelSize: 15; padding: 0; background: null; Layout.fillWidth: true
                        }
                        FocusScope {
                            id: fileResults
                            objectName: "miniFinderResults"
                            visible: desk.surface === "result" && desk.liveSnapshot.view === "finder"
                            Layout.fillWidth: true; implicitHeight: finderContent.implicitHeight
                            activeFocusOnTab: true
                            Accessible.role: Accessible.List
                            Accessible.name: "Danh sách file tìm được"
                            onActiveFocusChanged: { if (activeFocus && desk.selectedFinderIndex < 0 && desk.visibleFinderHits.length) desk.selectedFinderIndex = 0 }
                            Keys.onDownPressed: desk.selectFile(desk.selectedFinderIndex + 1)
                            Keys.onUpPressed: desk.selectFile(desk.selectedFinderIndex < 0 ? 0 : desk.selectedFinderIndex - 1)
                            Keys.onReturnPressed: event => { event.accepted=true; if (desk.selectedFinderIndex >= 0) { if (event.modifiers & Qt.MetaModifier) desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex); else desk.liveController.openSelectedHit(desk.selectedFinderIndex) } }
                            Keys.onEnterPressed: event => { event.accepted=true; if (desk.selectedFinderIndex >= 0) { if (event.modifiers & Qt.MetaModifier) desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex); else desk.liveController.openSelectedHit(desk.selectedFinderIndex) } }
                            ColumnLayout {
                                id: finderContent; width: parent.width; spacing: 5
                                Repeater {
                                    id: fileRows
                                    model: desk.visibleFinderHits
                                    delegate: Rectangle {
                                        required property var modelData
                                        required property int index
                                        Layout.fillWidth: true; implicitHeight: hitColumn.implicitHeight + 18; radius: 9
                                        color: desk.selectedFinderIndex === index ? desk.selectedSurface : fileMouse.containsMouse ? desk.hoverSurface : "transparent"
                                        border.color: desk.selectedFinderIndex === index && fileResults.activeFocus ? desk.accent : "transparent"
                                        ColumnLayout {
                                            id: hitColumn; x: 9; y: 9; width: parent.width - 18; spacing: 3
                                            Label { text: modelData.title; textFormat: Text.PlainText; color: desk.ink; font.weight: Font.Medium; font.pixelSize: 14; elide: Text.ElideRight; Layout.fillWidth: true }
                                            Label { text: modelData.path; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 11; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                        }
                                        MouseArea { id: fileMouse; anchors.fill: parent; hoverEnabled: true; onClicked: desk.selectFile(index); onDoubleClicked: { desk.selectFile(index); desk.liveController.openSelectedHit(index) } }
                                        Accessible.role: Accessible.ListItem; Accessible.name: modelData.title + ", " + modelData.path
                                    }
                                }
                                QuietButton { visible: desk.allFinderHits.length > 5; text: desk.showAllFinderHits ? "Hiện ít hơn" : "Xem thêm " + (desk.allFinderHits.length - 5) + " file"; onClicked: { desk.showAllFinderHits = !desk.showAllFinderHits; if (desk.selectedFinderIndex >= desk.visibleFinderHits.length) desk.selectedFinderIndex = -1 } }
                                Label { visible: desk.allFinderHits.length > 0; text: "Chọn file · ↑↓ di chuyển · Enter mở khi đang ở danh sách"; color: desk.muted; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            }
                        }
                        ColumnLayout {
                            visible: desk.surface === "result" && desk.liveSnapshot.view === "organization"; Layout.fillWidth: true; spacing: 10
                            Label { text: desk.liveSnapshot.meta || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { text: "Giữ nguyên tên và nội dung. Không ghi đè file. Chỉ xử lý file ngay trong thư mục đã chọn."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Repeater {
                                model: desk.liveSnapshot.organizationGroups || []
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true; spacing: 5
                                    QuietButton { text: modelData.name + " · " + modelData.count + " file"; iconName: desk.expandedGroups[modelData.name] ? "chevron-up" : "chevron-down"; onClicked: desk.toggleGroup(modelData.name) }
                                    Repeater {
                                        model: desk.expandedGroups[modelData.name] ? modelData.rows : []
                                        delegate: ColumnLayout {
                                            required property var modelData
                                            Layout.fillWidth: true; spacing: 2
                                            Label { text: modelData.name; textFormat: Text.PlainText; color: desk.ink; Layout.fillWidth: true; elide: Text.ElideMiddle }
                                            Label { text: "→ " + modelData.destination + (modelData.state === "preview" ? "" : " · " + ({moved:"Đã chuyển",undone:"Đã hoàn tác",skipped:"Bỏ qua",undo_conflict:"Chưa hoàn tác được",move_pending:"Cần phục hồi",undo_pending:"Cần phục hồi",identity_conflict:"File đã đổi",restored_conflict:"Đã trả lại"}[modelData.state] || modelData.state)); textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                                        }
                                    }
                                }
                            }
                            Label { visible: Boolean((desk.liveSnapshot.organization || {}).limited); text: "Bản xem trước đã đạt giới hạn. Xem kết quả lượt này trước khi tạo lượt mới."; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        }
                        }
                    }
                }
                Label { visible: !desk.auxiliary && Boolean(desk.liveSnapshot.settingsNotice); text: desk.liveSnapshot.settingsNotice || ""; color: desk.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Label { visible: (desk.surface === "settings" && Boolean(desk.settingsError)) || (desk.auxiliary && !desk.liveSnapshot.setupCompleted && Boolean(desk.setupError)); text: desk.surface === "settings" ? desk.settingsError : desk.setupError; color: desk.pdfInk; wrapMode: Text.Wrap; Layout.fillWidth: true }
                // Actions stay outside the scrolling content, pinned to the current artifact.
                RowLayout {
                    visible: desk.previewing || desk.noticeVisible; Layout.fillWidth: true
                    QuietButton { text: "Quay lại"; onClicked: desk.liveController.returnToTask() }
                    Label { visible: Boolean(desk.liveSnapshot.pendingPreviewHasNewer); text: "Có đoạn mới chờ"; color: desk.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: desk.noticeVisible; text: "Dán chữ"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.pasteSelectionFallback() }
                    QuietButton { visible: desk.noticeVisible && desk.liveSnapshot.selectionNeedsPermission; text: "Mở Trợ năng…"; primary: true; onClicked: desk.liveController.openSelectionAccess() }
                    QuietButton { visible: desk.previewing && desk.liveSnapshot.pendingPreviewHasText; text: "Dịch đoạn này"; primary: true; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.openPendingLook() }
                }
                RowLayout {
                    visible: desk.auxiliary; Layout.fillWidth: true
                    QuietButton { text: desk.surface === "help" ? "Cài đặt…" : "Quay lại"; visible: desk.surface !== "welcome"; onClicked: { if (desk.surface === "help") desk.openSettings(); else desk.goBack() } }
                    QuietButton { visible: desk.surface === "help" && desk.liveSnapshot.readinessBusy; text: "Dừng"; onClicked: desk.liveController.cancel() }
                    QuietButton { visible: desk.surface === "help" && !desk.liveSnapshot.readinessBusy; text: desk.liveSnapshot.readinessBusy ? "Đang kiểm tra…" : "Kiểm tra"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.checkReadiness(true) }
                    Item { Layout.fillWidth: true }
                    QuietButton {
                        id: setupPrimary; objectName: "helloContinue"; primary: true
                        enabled: !desk.liveSnapshot.busy && (desk.surface !== "welcome" || desk.liveSnapshot.setupCompleted || desk.liveSnapshot.accessibilityReady)
                        text: desk.surface === "settings" ? "Lưu" : desk.liveSnapshot.setupCompleted ? "Về RAT" : "Bắt đầu"
                        onClicked: {
                            if (desk.surface === "settings") {
                                desk.settingsError = desk.liveController.savePreferences({roots:folderList.model,source_language:sourceLanguage.currentValue,target_language:targetLanguage.currentValue,translation_provider:backend.currentValue || "automatic",free_fallback:freeFallback.checked,provider:cloudProvider.currentValue,model:cloudModel.text,llm_enabled:llmEnabled.checked}, providerKey.text)
                                if (!desk.settingsError) { providerKey.clear(); desk.goBack() }
                            } else if (!desk.liveSnapshot.setupCompleted) desk.setupError = desk.liveController.completeSetup()
                            else desk.goBack()
                        }
                    }
                }
                RowLayout {
                    visible: !desk.simpleAnswer && desk.paperVisible && !desk.auxiliary && !desk.liveSnapshot.busy && desk.taskVisible; Layout.fillWidth: true; spacing: 5
                    QuietButton { visible: desk.surface === "ocr"; text: "Chữ ban đầu"; onClicked: desk.navigate("source") }
                    QuietButton { visible: desk.surface === "ocr"; text: "Xem ảnh"; enabled: Boolean(desk.liveSnapshot.imagePreviewUrl); onClicked: desk.navigate("image") }
                    QuietButton { visible: !desk.compact && desk.surface === "result" && Boolean(desk.liveSnapshot.hasOcrSource); text: "Sửa chữ"; enabled: !desk.liveSnapshot.busy; onClicked: desk.navigate("ocr") }
                    QuietButton { visible: !desk.compact && desk.surface === "result" && Boolean(desk.liveSnapshot.imagePreviewUrl); text: "Xem ảnh"; onClicked: desk.navigate("image") }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "finder" && desk.liveSnapshot.phase === "partial" && desk.allFinderHits.length > 0 && desk.liveSnapshot.finderSettingsSuggested; text: "Thư mục…"; onClicked: desk.openSettings() }
                    QuietButton { visible: !desk.compact && desk.surface === "result" && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0; text: "Hiện trong Finder"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex) }
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: !desk.liveSnapshot.busy && desk.recoveryVisible && Boolean(desk.recoveryAction); primary: true; text: ({journal:"Xem nhật ký",image:"Chọn ảnh khác…",settings:"Mở cài đặt",retry:(["open_file","reveal_file"].indexOf(desk.liveSnapshot.lastOperation)>=0 ? "Tìm lại" : "Thử lại")}[desk.recoveryAction] || ""); onClicked: desk.recover() }
                    QuietButton { visible: desk.surface === "ocr" && !desk.recoveryVisible; primary: true; text: "Dịch lại"; enabled: !desk.liveSnapshot.busy && desk.liveSnapshot.canRetryTranslation && Boolean((desk.liveSnapshot.ocrText || "").trim()); onClicked: desk.liveController.retryTranslation(desk.liveSnapshot.ocrText) }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "finder" && !desk.recoveryVisible; primary: true; text: "Mở file"; enabled: !desk.liveSnapshot.busy && desk.selectedFinderIndex >= 0; onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex) }
                    QuietButton {
                        visible: desk.compact && desk.surface === "result" && desk.liveSnapshot.view === "organization" && !desk.recoveryVisible
                        primary: true; text: desk.liveSnapshot.canApplyOrganization ? "Xem kế hoạch" : "Xem biên nhận"
                        onClicked: { desk.saveScroll(); desk.liveController.setExpanded(true) }
                    }
                    QuietButton { objectName: "applyOrganization"; visible: !desk.compact && desk.surface === "result" && desk.liveSnapshot.view === "organization" && Boolean(desk.liveSnapshot.canApplyOrganization) && !desk.recoveryVisible; primary: true; text: "Áp dụng"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.applyOrganization() }
                    QuietButton { objectName: "undoOrganization"; visible: !desk.compact && desk.surface === "result" && desk.liveSnapshot.view === "organization" && Boolean(desk.liveSnapshot.canUndoOrganization) && !desk.recoveryVisible; primary: true; text: "Hoàn tác"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.undoOrganization() }
                }
            }
        }
        SpeechSurface {
            id: composer
            objectName: "composer"
            visible: !desk.auxiliary && desk.composing
            y: desk.bodyVisible ? resultSheet.height : 0
            width: parent.width
            height: Math.max(48, composerColumn.implicitHeight + 16)
            cornerRadius: 18; padding: 14
            paperColor: "transparent"; edgeColor: "transparent"
            tailEnabled: false
            anchorPoint: Qt.point(desk.ratX + headPose.speechAnchor.x - panel.x - x,
                                 desk.ratY + headPose.speechAnchor.y - panel.y - y)
            TextMetrics { id: composerMeasure; text: editor.text; font: editor.font }
            ColumnLayout {
                id: composerColumn
                x: 8; y: 8; width: parent.width - 16; spacing: 4
                RowLayout {
                    visible: Boolean(desk.liveSnapshot.hotkeyStatus || desk.liveSnapshot.shortcutAck || desk.liveSnapshot.hotkeyStarting)
                    Layout.fillWidth: true; spacing: 4
                    Label {
                        text: desk.liveSnapshot.hotkeyStarting ? "Đang kết nối phím tắt…" : desk.liveSnapshot.shortcutAck ? "Đang bận · bấm lại khi xong" : desk.liveSnapshot.hotkeyStatus ? "Phím tắt chưa sẵn sàng" : "Quick Look · " + desk.liveSnapshot.shortcutLabel
                        textFormat: Text.PlainText; font.pixelSize: 12; color: desk.muted
                        Layout.fillWidth: true; wrapMode: Text.Wrap
                    }
                    QuietButton { visible: Boolean(desk.liveSnapshot.hotkeyStatus); enabled: !desk.liveSnapshot.hotkeyStarting; text: "Kết nối lại"; onClicked: desk.liveController.restartHotkey() }
                }
                RowLayout {
                    visible: !desk.auxiliary && Boolean(desk.liveSnapshot.editingRequest); Layout.fillWidth: true
                    Label { text: "Đang sửa yêu cầu cũ · bản nháp mới vẫn được giữ"; color: desk.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    QuietButton { text: "Hủy sửa"; onClicked: desk.liveController.cancelEditRequest() }
                }
                Rectangle {
                    visible: !desk.auxiliary; Layout.fillWidth: true
                    implicitHeight: composerRow.implicitHeight; color: "transparent"
                    RowLayout {
                        id: composerRow; width: parent.width; spacing: 8
                        ScrollView {
                            Layout.fillWidth: true; Layout.preferredHeight: Math.min(78, Math.max(30, editor.contentHeight + 4))
                            contentWidth: availableWidth; clip: true; ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            TextArea {
                                id: editor; objectName: "miniEditor"
                                activeFocusOnTab: true
                                KeyNavigation.priority: KeyNavigation.BeforeItem
                                KeyNavigation.tab: sendControl
                                KeyNavigation.backtab: closeControl
                                placeholderText: desk.liveSnapshot.editingRequest ? "Sửa yêu cầu…" : desk.liveSnapshot.busy ? "Soạn tiếp…" : desk.liveSnapshot.phase === "needs_input" ? "Trả lời Chuột…" : "Bạn cần gì?"
                                color: desk.ink; placeholderTextColor: desk.muted; font.pixelSize: desk.sharedTextSize
                                textFormat: TextEdit.PlainText; selectByMouse: true; wrapMode: TextEdit.Wrap; padding: 0; topPadding: 4; selectionColor: desk.accent; selectedTextColor: desk.accentText; background: null
                                Accessible.name: "Yêu cầu RAT Mini"
                                onActiveFocusChanged: { if (activeFocus) desk.keyboardOwner="composer" }
                                onTextChanged: {
                                    if (!desk.syncingDraft) desk.liveController.setComposerDraft(text)
                                    Qt.callLater(desk.growComposerWidth)
                                }
                                Keys.onPressed: event => { if (event.matches(StandardKey.Paste)) { event.accepted=true; desk.pasteDraft() } }
                                Keys.onReturnPressed: event => { if (event.modifiers & Qt.ShiftModifier) event.accepted=false; else { event.accepted=true; desk.liveController.submitDraft() } }
                                Keys.onEnterPressed: event => { if (event.modifiers & Qt.ShiftModifier) event.accepted=false; else { event.accepted=true; desk.liveController.submitDraft() } }
                                MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton; onClicked: editorMenu.popup() }
                            }
                        }
                        QuietButton { id: sendControl; KeyNavigation.tab: moreControl; KeyNavigation.backtab: editor; objectName: "sendButton"; primary: true; iconName: "arrow-up"; implicitWidth: 28; implicitHeight: 28; enabled: !desk.liveSnapshot.busy && Boolean(editor.text.trim() || desk.liveSnapshot.attachmentLabel); Accessible.name: "Gửi yêu cầu"; onClicked: desk.liveController.submitDraft() }
                        QuietButton { id: moreControl; KeyNavigation.tab: closeControl; KeyNavigation.backtab: editor; visible: true; text: "⋯"; implicitWidth: 20; Accessible.name: "Thao tác khác"; onClicked: moreMenu.popup() }
                        QuietButton { id: closeControl; KeyNavigation.tab: editor; KeyNavigation.backtab: moreControl; visible: true; iconName: "close"; implicitWidth: 20; Accessible.name: "Ẩn RAT"; onClicked: desk.hideRequested() }
                    }
                }
            }
        }
    }
    Item {
        id: mascotItem; objectName: "mascotCrop"
        x: desk.ratX; y: desk.ratY; width: desk.floatingHeadSize; height: desk.floatingHeadSize
        MascotPose {
            id: headPose; anchors.fill: parent; source: desk.lookIdleSource
            bottomPadding: 4; opticalHeight: desk.floatingHeadOpticalHeight
            inkBounds: Qt.rect(0.08, 0.06, 0.84, 0.89)
            mouth: Qt.point(0.43, 0.43)
        }
        MouseArea {
            id: headMouse; anchors.fill: parent; hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            property point pressPoint; property bool draggingHead: false
            cursorShape: Qt.OpenHandCursor
            onPressed: mouse => { pressPoint = Qt.point(mouse.x, mouse.y); draggingHead = false }
            onPositionChanged: mouse => {
                if (pressed && (pressedButtons & Qt.LeftButton) && !draggingHead &&
                    (Math.abs(mouse.x - pressPoint.x) > 4 || Math.abs(mouse.y - pressPoint.y) > 4)) {
                    draggingHead = true; desk.moveRequested()
                }
            }
            onClicked: mouse => {
                if (mouse.button === Qt.RightButton) moreMenu.popup()
                else if (!draggingHead) desk.liveController.toggleComposer()
            }
        }
        ToolTip.visible: headMouse.containsMouse && !headMouse.pressed
        ToolTip.delay: 500
        ToolTip.text: (desk.liveSnapshot.pinned ? "Đang ghim · " : "") + "Quick Look · " + desk.liveSnapshot.shortcutLabel + " · Bấm để viết"
        Accessible.role: Accessible.Button
        Accessible.name: "RAT Lite. Bấm mở hoặc đóng ô nhập; chuột phải mở menu; kéo để di chuyển."
        Accessible.onPressAction: desk.liveController.toggleComposer()
    }
    Rectangle {
        visible: Boolean(desk.liveSnapshot.dropActive)
        x: panel.x; y: panel.y; width: panel.width; height: panel.height; radius: 14
        color: desk.selectedSurface; border.color: desk.accent; border.width: 2
        Label { anchors.centerIn: parent; text: "Thả ảnh để dịch"; color: desk.ink; font.pixelSize: 16 }
    }
    Shortcut { enabled: !desk.auxiliary && !desk.composing; context: Qt.ApplicationShortcut; sequences: [StandardKey.Paste]; onActivated: desk.liveController.pasteLook() }
    Shortcut { sequence: "Escape"; onActivated: { if (diagnosticDialog.visible) diagnosticDialog.close(); else if (imageDialog.visible) imageDialog.close(); else if (folderDialog.visible) folderDialog.close(); else if (historyMenu.visible) historyMenu.close(); else if (analysisMenu.visible) analysisMenu.close(); else if (moreMenu.visible) moreMenu.close(); else if (readerMenu.visible) readerMenu.close(); else if (editorMenu.visible) editorMenu.close(); else if (desk.previewing || desk.noticeVisible) desk.liveController.returnToTask(); else if (desk.auxiliary || desk.surface !== "result") desk.goBack(); else if (desk.composing) desk.liveController.toggleComposer(); else desk.liveController.collapseBubble() } }
    Shortcut { sequence: "Meta+W"; onActivated: desk.hideRequested() }
    Shortcut { sequence: "Meta+Q"; onActivated: desk.liveController.quit() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: desk.liveController.quit() }
    Shortcut { sequence: "Meta+,"; onActivated: desk.openSettings() }
    Menu {
        id: moreMenu
        // Qt 6.8+: the Look window can be just 122px wide. A separate popup
        // window keeps the secondary menu outside that tiny input mask.
        popupType: Popup.Window
        MenuItem { text: desk.liveSnapshot.pinned ? "Bỏ ghim" : "Ghim kết quả"; onTriggered: desk.liveController.togglePin() }
        Menu {
            id: historyMenu; title: "Công việc gần đây · trong RAM"; popupType: Popup.Window
            enabled: !desk.liveSnapshot.busy
            Instantiator {
                model: desk.liveSnapshot.taskHistory || []
                delegate: MenuItem { required property var modelData; text: modelData.title; onTriggered: desk.liveController.restoreTask(modelData.index) }
                onObjectAdded: (index, object) => historyMenu.insertItem(index, object)
                onObjectRemoved: (index, object) => historyMenu.removeItem(object)
            }
            MenuSeparator {}
            MenuItem { text: "Xóa lịch sử tạm"; onTriggered: desk.liveController.clearTaskHistory() }
        }
        MenuItem { visible: desk.liveSnapshot.hasWorkbench; text: "Mở Workbench"; onTriggered: { desk.saveScroll(); desk.navigate("workbench") } }
        MenuItem { text: "Xem lại công việc"; onTriggered: desk.liveController.summonLook() }
        MenuItem { text: "Viết yêu cầu"; onTriggered: desk.liveController.summonMinimal() }
        MenuItem { visible: desk.liveSnapshot.hasWorkbench; text: desk.compact ? "Mở rộng kết quả" : "Thu gọn"; onTriggered: desk.liveController.setExpanded(desk.compact) }
        MenuItem { text: "Quyền đọc chữ bôi đen…"; onTriggered: desk.liveController.openSelectionAccess() }
        MenuItem { text: !desk.liveSnapshot.lookWatching ? "Bật theo dõi Clipboard" : desk.liveSnapshot.lookPaused ? "Tiếp tục Clipboard" : "Tạm dừng Clipboard"; onTriggered: desk.liveController.toggleLookPaused() }
        MenuItem { visible: desk.liveSnapshot.lookWatching; text: "Tắt theo dõi Clipboard"; onTriggered: desk.liveController.stopLook() }
        MenuItem { visible: desk.liveSnapshot.lookHasQueued; text: "Xem đoạn chờ"; onTriggered: desk.liveController.previewPending() }
                MenuItem { enabled: !desk.liveSnapshot.busy; text: "Chọn vùng chữ để dịch…"; onTriggered: desk.liveController.captureRegion() }
        Menu {
            id: analysisMenu; popupType: Popup.Window; title: "Đọc tiếp từ nguồn"; enabled: desk.liveSnapshot.hasOcrSource && !desk.liveSnapshot.busy
            MenuItem { text: "Dịch lại · sát nghĩa"; onTriggered: desk.liveController.translateSource("faithful") }
            MenuItem { text: "Dịch lại · dễ hiểu · cloud"; onTriggered: desk.liveController.translateSource("plain") }
            MenuSeparator {}
            MenuItem { text: "Tóm tắt"; onTriggered: desk.liveController.analyzeSource("summary") }
            MenuItem { text: "Giải thích"; onTriggered: desk.liveController.analyzeSource("explanation") }
            MenuItem { text: "Thuật ngữ"; onTriggered: desk.liveController.analyzeSource("terms") }
            MenuItem { text: "Viết lại theo bản nháp"; onTriggered: desk.liveController.analyzeSource("rewrite") }
        }
        MenuItem {
            visible: Boolean(desk.liveSnapshot.translationDetails || desk.liveSnapshot.translationNotice)
            text: "Chi tiết kết quả…"
            onTriggered: { desk.saveScroll(); desk.showTranslationDetails=true; desk.liveController.setExpanded(true) }
        }
        MenuItem { visible: desk.liveSnapshot.hasOcrSource; text: "Nguồn và kết quả"; onTriggered: desk.liveController.toggleSource() }
        MenuItem { visible: desk.liveSnapshot.hasOcrSource; text: "Sửa chữ đã đọc…"; onTriggered: desk.navigate("ocr") }
        MenuItem { visible: Boolean(desk.liveSnapshot.imagePreviewUrl); text: "Xem ảnh nguồn…"; onTriggered: desk.navigate("image") }
        MenuItem { visible: Boolean(desk.liveSnapshot.hotkeyStatus); enabled: !desk.liveSnapshot.hotkeyStarting; text: "Đăng ký lại phím tắt"; onTriggered: desk.liveController.restartHotkey() }
        MenuItem { text: "Chọn ảnh để dịch…"; enabled: !desk.liveSnapshot.busy && !desk.auxiliary; onTriggered: imageDialog.open() }
        MenuItem { text: "Dịch Clipboard"; enabled: !desk.liveSnapshot.busy; onTriggered: desk.liveController.translateClipboard() }
        MenuItem { text: "Sắp xếp thư mục…"; enabled: !desk.liveSnapshot.busy && !desk.auxiliary; onTriggered: { desk.folderPurpose="organize"; folderDialog.open() } }
        MenuItem { text: "Lần sắp xếp gần nhất / Hoàn tác"; enabled: !desk.liveSnapshot.busy; onTriggered: desk.liveController.recoverOrganization() }
        MenuSeparator {}
        MenuItem { text: "Cài đặt…"; onTriggered: desk.openSettings() }
        MenuItem { text: "Thiết lập & trợ giúp…"; onTriggered: desk.navigate("help") }
        MenuItem { enabled: false; text: "RAT Lite · " + desk.buildLabel }
        MenuItem { text: "Thoát RAT"; onTriggered: desk.liveController.quit() }
    }
    Menu {
        id: readerMenu
        popupType: Popup.Window
        property var sourceEditor: translationArea
        MenuItem { text: "Sao chép phần đã chọn"; enabled: Boolean(readerMenu.sourceEditor.selectedText); onTriggered: desk.liveController.copyLookSelection(readerMenu.sourceEditor.selectedText) }
        MenuItem { text: "Sao chép nội dung"; enabled: Boolean(readerMenu.sourceEditor.text); onTriggered: { if (readerMenu.sourceEditor === translationArea) desk.liveController.copyResult(); else desk.liveController.copyLookSelection(readerMenu.sourceEditor.text) } }
        MenuItem { text: desk.compact ? "Mở rộng" : "Thu gọn"; onTriggered: { desk.saveScroll(); desk.liveController.setExpanded(desk.compact) } }
    }
    Menu {
        id: editorMenu
        MenuItem { text: "Dán"; onTriggered: desk.pasteDraft() }
        MenuItem { text: "Sao chép"; enabled: Boolean(editor.selectedText); onTriggered: editor.copy() }
        MenuItem { text: "Cắt"; enabled: Boolean(editor.selectedText); onTriggered: editor.cut() }
    }
    FolderDialog {
        id: folderDialog
        title: desk.folderPurpose === "organize" ? "Chọn thư mục để xem trước" : "Chọn thư mục cho RAT"
        onAccepted: {
            if (desk.folderPurpose === "organize") { desk.liveController.organizeFolder(selectedFolder); return }
            var path = desk.liveController.localFolderPath(selectedFolder)
            if (path) { var roots=folderList.model.slice(); if (roots.indexOf(path)<0) roots.push(path); folderList.model=roots }
        }
    }
    FileDialog {
        id: diagnosticDialog; title: "Xuất chẩn đoán không kèm nội dung"; fileMode: FileDialog.SaveFile
        nameFilters: ["JSON (*.json)"]; defaultSuffix: "json"; selectedFile: "rat-lite-diagnostics.json"
        onAccepted: { var error=desk.liveController.exportDiagnostics(selectedFile); if (error) desk.liveController.reportDiagnosticError(error) }
    }
    FileDialog {
        id: imageDialog; title: "Chọn ảnh để dịch"; fileMode: FileDialog.OpenFile
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"]
        onAccepted: desk.liveController.chooseImageFile(selectedFile, desk.draftText)
    }
}
