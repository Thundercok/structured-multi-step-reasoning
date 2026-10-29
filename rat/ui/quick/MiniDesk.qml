import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

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
    property real lookMascotWidth: 176
    property real lookMascotHeight: 176
    property real lookOpticalHeight: 134
    property real sharedPanelWidth: 580
    property real sharedTextSize: 16
    property string buildLabel: "source"
    property real maxCornerSpeechHeight: 300
    property real composerWidthFloor: 380
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
    readonly property bool paperVisible: Boolean((!compact || surface !== "result") && liveSnapshot.hasWorkbench)
    readonly property bool bodyVisible: auxiliary || paperVisible
    readonly property bool ocrDirty: Boolean(liveSnapshot.ocrDirty)
    readonly property bool ocrPanelVisible: surface === "ocr"
    readonly property string draftText: editor.text
    readonly property var allFinderHits: liveSnapshot.finderHits || []
    readonly property var visibleFinderHits: showAllFinderHits ? allFinderHits : allFinderHits.slice(0, 5)
    // Only transient native input/menu ownership exempts outside dismissal.
    readonly property bool focusOwned: imageDialog.visible || folderDialog.visible || Boolean(targetLanguage.popup && targetLanguage.popup.visible) || Boolean(sourceLanguage.popup && sourceLanguage.popup.visible) || Boolean(backend.popup && backend.popup.visible) || Boolean(cloudProvider.popup && cloudProvider.popup.visible) || moreMenu.visible || editorMenu.visible || lookView.menuOpen || Boolean(liveSnapshot.dropActive)
    readonly property bool imageDropEnabled: !auxiliary && !imageDialog.visible && !folderDialog.visible
    readonly property bool layoutExpanded: !lookActive && bodyVisible
    readonly property real preferredPanelHeight: lookActive ? lookView.bubbleHeight : panel.height
    readonly property real lookBubbleWidth: lookView.preferredBubbleWidth
    readonly property real lookBubbleHeight: lookView.preferredBubbleHeight
    readonly property real cornerPanelWidth: Math.min(sharedPanelWidth, composerWidthFloor)
    readonly property string lookVariant: lookView.variant
    readonly property bool lookEngaged: lookActive && lookView.engaged
    readonly property rect cornerInkBounds: lookActive ? lookView.localVisualBounds : standingPose.visualBounds
    readonly property point cornerMouth: lookActive ? lookView.localMouth : standingPose.speechAnchor
    readonly property real paperOffset: Math.min(128, Math.max(0, panel.width - 300))
    readonly property rect panelRect: lookActive ? lookView.bubbleRect : Qt.rect(panel.x, panel.y, panel.width, panel.height)
    readonly property rect mascotRect: lookActive ? lookView.mascotRect : Qt.rect(mascotItem.x, mascotItem.y, mascotItem.width, mascotItem.height)
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
    readonly property string title: surface === "welcome" ? "Xin chào, mình là RAT" : surface === "help" ? "Thiết lập & trợ giúp" : surface === "settings" ? "Cài đặt" : surface === "ocr" ? "Sửa chữ trong ảnh" : surface === "image" ? "Ảnh nguồn" : surface === "source" ? "Chữ nhận ban đầu" : !paperVisible ? "RAT" : liveSnapshot.view === "finder" ? "File tìm được" : liveSnapshot.view === "organization" ? "Sắp xếp thư mục" : liveSnapshot.view === "translation" ? "Bản dịch" : "Yêu cầu của bạn"
    signal moveRequested()
    signal hideRequested()

    Component.onCompleted: {
        liveSnapshot = liveController.snapshot
        editor.text = liveSnapshot.draftText || ""
    }
    function saveScroll() { liveController.rememberScroll(resultScroll.contentY) }
    function navigate(next) { saveScroll(); liveController.showSurface(next); if (next !== "image") Qt.callLater(focusComposer) }
    function goBack() { saveScroll(); liveController.backSurface(); Qt.callLater(function() { if (!desk.lookActive) focusComposer(); else restoreReader() }) }
    function restoreReader() {
        if (lookActive) lookView.restoreReading()
        else if (!auxiliary && surface === "result" && translationArea.visible) {
            var saved = liveController.snapshot
            restoringScroll = true
            if (saved.readerAnchorText === translationArea.text && translationArea.text.length > 0) {
                var origin = translationArea.mapToItem(resultScroll.contentItem, 0, 0).y
                var rect = translationArea.positionToRectangle(Math.min(saved.readerAnchorPosition, translationArea.length))
                resultScroll.contentY = Math.max(0, Math.min(origin + rect.y + saved.readerAnchorDelta,
                    Math.max(0, resultScroll.contentHeight - resultScroll.height)))
            }
            translationArea.select(saved.lookSelectionStart || 0, saved.lookSelectionEnd || 0)
            restoringScroll = false
        }
    }
    function growComposerWidth() {
        if (compact && !auxiliary)
            composerWidthFloor = Math.max(composerWidthFloor,
                composer.widthStepFor(composerMeasure.advanceWidth + 92, sharedPanelWidth))
    }
    function beginCornerPresentation() {
        // A fresh invocation may choose a smaller tier; typing/clearing during
        // the invocation only grows it, avoiding a collapse when Send clears it.
        lookView.beginPresentation()
        if (compact)
            composerWidthFloor = composer.widthStepFor(Math.max(300, composerMeasure.advanceWidth + 92), sharedPanelWidth)
    }
    function focusComposer() {
        if (composing && !auxiliary && surface === "result") editor.forceActiveFocus()
        else if (lookActive) lookView.focusSurface()
        else if (surface === "ocr" && paperVisible) ocrEditor.forceActiveFocus()
        else if (surface === "settings") targetLanguage.forceActiveFocus()
        else if (auxiliary) setupPrimary.forceActiveFocus()
        else if (keyboardOwner === "files" && paperVisible && liveSnapshot.view === "finder") fileResults.forceActiveFocus()
        else editor.forceActiveFocus()
    }
    function dismissTransient() { moreMenu.close(); editorMenu.close(); providerKey.clear() }
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
            lookView.prepareSnapshot(next)
            var moved = next.surface !== desk.surface || next.taskId !== desk.liveSnapshot.taskId || next.interactionExtent !== desk.liveSnapshot.interactionExtent
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

    // Expanded task projection. The same composer moves into the compact bubble.
    Item {
        id: panel
        visible: !desk.lookActive
        x: desk.panelX; y: desk.panelY
        width: Math.max(1, desk.panelWidth)
        height: desk.auxiliary ? resultSheet.height : (desk.composing ? composer.height : 0) + (desk.bodyVisible ? resultSheet.height : 0)
        Rectangle {
            id: resultSheet
            visible: desk.bodyVisible
            x: 0
            width: parent.width
            height: Math.min(desk.maxPanelHeight - (desk.auxiliary || !desk.composing ? 0 : composer.height), paperColumn.implicitHeight + (desk.auxiliary ? 28 : 50))
            radius: 16; color: desk.paperColor; border.color: desk.edge
            Rectangle {
                id: fullSource
                visible: Boolean(desk.liveSnapshot.sourceVisible) && !desk.auxiliary && parent.width >= 700
                x: 22; y: 14; width: Math.min(260, parent.width * 0.32)
                height: parent.height - 50; radius: 10; color: desk.utilitySurface
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 10; spacing: 8
                    Label { text: "Nguồn đang dùng"; color: desk.muted; font.pixelSize: 11 }
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
                x: fullSource.visible ? fullSource.width + 34 : 22
                y: 14; width: parent.width - x - 22
                height: parent.height - (desk.auxiliary ? 28 : 50); spacing: 10
                RowLayout {
                    Layout.fillWidth: true; spacing: 6
                    QuietButton { visible: desk.auxiliary || (desk.paperVisible && desk.surface !== "result"); iconName: "arrow-left"; implicitWidth: 30; Accessible.name: "Quay lại"; onClicked: desk.goBack() }
                    Label { text: desk.title; textFormat: Text.PlainText; color: desk.ink; font.pixelSize: 11; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                    BusyIndicator { running: Boolean(desk.liveSnapshot.busy); visible: running; implicitWidth: 18; implicitHeight: 18 }
                    QuietButton { visible: desk.paperVisible && !desk.auxiliary; text: "Nguồn"; onClicked: desk.liveController.toggleSource() }
                    QuietButton { visible: desk.paperVisible && !desk.auxiliary && !desk.composing; text: "Viết yêu cầu"; onClicked: desk.liveController.summonMinimal() }
                    QuietButton { visible: desk.paperVisible && !desk.auxiliary; iconName: "chevron-down"; implicitWidth: 28; Accessible.name: "Thu gọn"; onClicked: desk.liveController.setExpanded(false) }
                }
                RowLayout {
                    visible: desk.paperVisible && !desk.auxiliary && Boolean(desk.liveSnapshot.requestText)
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
                    visible: desk.paperVisible && !desk.auxiliary && Boolean(desk.liveSnapshot.status)
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
                    ScrollBar.vertical: ScrollBar {}
                    onContentYChanged: {
                        if (!desk.restoringScroll && visible) {
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
                        width: resultScroll.width; spacing: 12
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
                            visible: desk.surface === "welcome"; Layout.fillWidth: true; spacing: 14
                            Label { text: "Gõ điều bạn cần. Chuột sẽ tìm file hoặc dịch giúp bạn."; color: desk.ink; font.pixelSize: 21; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { text: "Chụp bằng ⌘⇧4, rồi thả ảnh vào đây. Bạn cũng có thể dán bằng ⌘V."; color: desk.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                            Label { text: "Anh ↔ Việt dịch trên máy. Esc để ẩn; bấm biểu tượng RAT trên menu bar để gọi lại."; color: desk.muted; wrapMode: Text.Wrap; Layout.fillWidth: true; font.pixelSize: 12 }
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
                            visible: desk.surface === "result" && desk.liveSnapshot.view === "translation"; Layout.fillWidth: true; spacing: 8
                            TextArea { id: translationArea; objectName: "translationText";
                                onSelectedTextChanged: { if (!desk.restoringScroll && visible) desk.liveController.rememberLookSelection(selectionStart, selectionEnd) }
                                Keys.onPressed: event => { if (event.matches(StandardKey.Copy) && selectedText.length > 0) { event.accepted = true; desk.liveController.copyLookSelection(selectedText) } }
                                 text: desk.liveSnapshot.text || ""; textFormat: TextEdit.PlainText; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: desk.ink; font.pixelSize: 16; padding: 0; background: null; Layout.fillWidth: true; Accessible.name: "Bản dịch" }
                            Label { visible: desk.ocrDirty; text: "Bản dịch này chưa dùng các chỉnh sửa chữ mới nhất."; color: desk.pdfInk; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { text: desk.liveSnapshot.meta || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Label { visible: Boolean(desk.liveSnapshot.translationNotice); text: desk.liveSnapshot.translationNotice || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            QuietButton { text: desk.showTranslationDetails ? "Ẩn chi tiết" : "Chi tiết"; onClicked: desk.showTranslationDetails = !desk.showTranslationDetails }
                            Label { visible: desk.showTranslationDetails; text: desk.liveSnapshot.translationDetails || ""; textFormat: Text.PlainText; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
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
                Label { visible: !desk.auxiliary && Boolean(desk.liveSnapshot.settingsNotice); text: desk.liveSnapshot.settingsNotice || ""; color: desk.muted; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Label { visible: (desk.surface === "settings" && Boolean(desk.settingsError)) || (desk.auxiliary && !desk.liveSnapshot.setupCompleted && Boolean(desk.setupError)); text: desk.surface === "settings" ? desk.settingsError : desk.setupError; color: desk.pdfInk; wrapMode: Text.Wrap; Layout.fillWidth: true }
                // Actions stay outside the scrolling content, pinned to the current artifact.
                RowLayout {
                    visible: desk.auxiliary; Layout.fillWidth: true
                    QuietButton { text: desk.surface === "help" ? "Cài đặt…" : "Quay lại"; visible: desk.surface !== "welcome"; onClicked: { if (desk.surface === "help") desk.openSettings(); else desk.goBack() } }
                    QuietButton { visible: desk.surface === "help" && desk.liveSnapshot.readinessBusy; text: "Dừng"; onClicked: desk.liveController.cancel() }
                    QuietButton { visible: desk.surface === "help" && !desk.liveSnapshot.readinessBusy; text: desk.liveSnapshot.readinessBusy ? "Đang kiểm tra…" : "Kiểm tra"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.checkReadiness(true) }
                    Item { Layout.fillWidth: true }
                    QuietButton {
                        id: setupPrimary; objectName: "helloContinue"; primary: true
                        enabled: !desk.liveSnapshot.busy
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
                    visible: desk.paperVisible && !desk.auxiliary && !desk.liveSnapshot.busy; Layout.fillWidth: true; spacing: 5
                    QuietButton { visible: desk.surface === "ocr"; text: "Chữ ban đầu"; onClicked: desk.navigate("source") }
                    QuietButton { visible: desk.surface === "ocr"; text: "Xem ảnh"; enabled: Boolean(desk.liveSnapshot.imagePreviewUrl); onClicked: desk.navigate("image") }
                    QuietButton { visible: desk.surface === "result" && Boolean(desk.liveSnapshot.hasOcrSource); text: "Sửa chữ"; enabled: !desk.liveSnapshot.busy; onClicked: desk.navigate("ocr") }
                    QuietButton { visible: desk.surface === "result" && Boolean(desk.liveSnapshot.imagePreviewUrl); text: "Xem ảnh"; onClicked: desk.navigate("image") }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "translation" && desk.liveSnapshot.phase === "partial" && Boolean(desk.liveSnapshot.text); text: "Sao chép phần đã dịch"; onClicked: desk.liveController.copyResult() }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "finder" && desk.liveSnapshot.phase === "partial" && desk.allFinderHits.length > 0 && desk.liveSnapshot.finderSettingsSuggested; text: "Thư mục…"; onClicked: desk.openSettings() }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0; text: "Hiện trong Finder"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.revealSelectedInFinder(desk.selectedFinderIndex) }
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: !desk.liveSnapshot.busy && desk.recoveryVisible && Boolean(desk.recoveryAction); primary: true; text: ({journal:"Xem nhật ký",image:"Chọn ảnh khác…",settings:"Mở cài đặt",retry:(["open_file","reveal_file"].indexOf(desk.liveSnapshot.lastOperation)>=0 ? "Tìm lại" : "Thử lại")}[desk.recoveryAction] || ""); onClicked: desk.recover() }
                    QuietButton { visible: desk.surface === "ocr" && !desk.recoveryVisible; primary: true; text: "Dịch lại"; enabled: !desk.liveSnapshot.busy && desk.liveSnapshot.canRetryTranslation && Boolean((desk.liveSnapshot.ocrText || "").trim()); onClicked: desk.liveController.retryTranslation(desk.liveSnapshot.ocrText) }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "translation" && !desk.recoveryVisible; primary: true; text: "Sao chép"; enabled: !desk.liveSnapshot.busy && Boolean(desk.liveSnapshot.text); onClicked: desk.liveController.copyResult() }
                    QuietButton { visible: desk.surface === "result" && desk.liveSnapshot.view === "finder" && !desk.recoveryVisible; primary: true; text: "Mở file"; enabled: !desk.liveSnapshot.busy && desk.selectedFinderIndex >= 0; onClicked: desk.liveController.openSelectedHit(desk.selectedFinderIndex) }
                    QuietButton { objectName: "applyOrganization"; visible: desk.surface === "result" && desk.liveSnapshot.view === "organization" && Boolean(desk.liveSnapshot.canApplyOrganization) && !desk.recoveryVisible; primary: true; text: "Áp dụng"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.applyOrganization() }
                    QuietButton { objectName: "undoOrganization"; visible: desk.surface === "result" && desk.liveSnapshot.view === "organization" && Boolean(desk.liveSnapshot.canUndoOrganization) && !desk.recoveryVisible; primary: true; text: "Hoàn tác"; enabled: !desk.liveSnapshot.busy; onClicked: desk.liveController.undoOrganization() }
                }
            }
        }
        SpeechSurface {
            id: composer
            objectName: "composer"
            parent: desk.lookActive ? lookView.composerHost : panel
            visible: !desk.auxiliary && desk.composing
            y: desk.lookActive ? 0 : desk.bodyVisible ? resultSheet.height : 0
            width: parent.width
            height: Math.max(94, composerColumn.implicitHeight + 26)
            cornerRadius: 18; padding: 14
            paperColor: desk.lookActive ? "transparent" : desk.inputColor; edgeColor: desk.lookActive ? "transparent" : desk.edge
            tailEnabled: false
            anchorPoint: Qt.point(desk.ratX + standingPose.speechAnchor.x - panel.x - x,
                                 desk.ratY + standingPose.speechAnchor.y - panel.y - y)
            TextMetrics { id: composerMeasure; text: editor.text; font: editor.font }
            ColumnLayout {
                id: composerColumn
                x: 14; y: 13; width: parent.width - 28; spacing: 7
                Label {
                    visible: !desk.liveSnapshot.hasWorkbench && !desk.liveSnapshot.busy
                    text: "Bôi đen chữ trong app khác → ⌥⇧Space"
                    textFormat: Text.PlainText; font.pixelSize: 12; color: desk.muted
                    Layout.fillWidth: true; wrapMode: Text.Wrap
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
                                placeholderText: desk.liveSnapshot.editingRequest ? "Sửa yêu cầu…" : desk.liveSnapshot.busy ? "Soạn yêu cầu tiếp theo…" : desk.liveSnapshot.phase === "needs_input" ? "Trả lời Chuột…" : desk.compact ? "Chuột ơi, coi nè · thả ảnh hoặc ⌘V…" : desk.paperVisible ? "Yêu cầu tiếp theo…" : "Chuột nghe đây. Bạn cần gì?"
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
                        QuietButton { objectName: "sendButton"; primary: true; iconName: desk.liveSnapshot.busy ? "stop" : "arrow-up"; implicitWidth: 32; implicitHeight: 32; enabled: Boolean(desk.liveSnapshot.busy || editor.text.trim() || desk.liveSnapshot.attachmentLabel); Accessible.name: desk.liveSnapshot.busy ? "Dừng yêu cầu" : "Gửi yêu cầu"; onClicked: { if (desk.liveSnapshot.busy) desk.liveController.cancel(); else desk.liveController.submitDraft() } }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 5
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: !desk.paperVisible && Boolean(desk.liveSnapshot.hasWorkbench); iconName: "chevron-up"; implicitWidth: 28; Accessible.name: "Mở lại kết quả"; onClicked: desk.liveController.openLookWorkbench() }
                    QuietButton { objectName: "attachImageButton"; iconName: "paperclip"; implicitWidth: 32; implicitHeight: 32; enabled: !desk.liveSnapshot.busy; Accessible.name: "Chọn ảnh để dịch"; ToolTip.visible: hovered; ToolTip.text: "Chọn ảnh"; onClicked: imageDialog.open() }
                    QuietButton { text: "⋯"; implicitWidth: 28; Accessible.name: "Thao tác khác"; onClicked: moreMenu.popup() }
                    QuietButton { iconName: "close"; implicitWidth: 28; Accessible.name: "Ẩn RAT"; onClicked: desk.hideRequested() }
                }
            }
        }
    }
    Item {
        id: mascotItem; objectName: "mascotCrop"
        visible: !desk.lookActive
        x: desk.ratX; y: desk.ratY; width: desk.lookMascotWidth; height: desk.lookMascotHeight
        Behavior on x { enabled: desk.animatePlacement && !desk.reduceMotion; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on y { enabled: desk.animatePlacement && !desk.reduceMotion; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        MascotPose {
            id: standingPose
            objectName: "standingOpticalPose"
            anchors.fill: parent; source: desk.failed ? desk.lookErrorSource : desk.lookIdleSource
            bottomPadding: 30
            inkBounds: desk.failed ? Qt.rect(0.04, 0.06, 0.92, 0.87) : Qt.rect(0.08, 0.06, 0.86, 0.88)
            mouth: desk.failed ? Qt.point(0.43, 0.40) : Qt.point(0.44, 0.43)
            opticalHeight: desk.lookOpticalHeight
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.SizeAllCursor; onPressed: desk.moveRequested() }
        CompanionStatus {
            objectName: "composerStatus"; z: 2
            x: (parent.width - width) / 2
            y: parent.height - height
            label: desk.liveSnapshot.lookHasQueued ? "đoạn chờ" : desk.liveSnapshot.busy ? "Đang xử lý" : "Sẵn sàng"
            pending: Boolean(desk.liveSnapshot.lookHasQueued); busy: Boolean(desk.liveSnapshot.busy)
            paperColor: desk.inputColor; inkColor: desk.ink; edgeColor: desk.edge
            onClicked: { if (desk.liveSnapshot.lookHasQueued) desk.liveController.previewPending(); else desk.liveController.openLook() }
        }
    }
    Rectangle {
        visible: !desk.lookActive && Boolean(desk.liveSnapshot.dropActive)
        x: panel.x; y: panel.y; width: panel.width; height: panel.height; radius: 16
        color: desk.selectedSurface; border.color: desk.accent; border.width: 2
        Label { anchors.centerIn: parent; text: "Thả ảnh để dịch"; color: desk.ink; font.pixelSize: 18 }
    }
    LookSurface {
        id: lookView
        anchors.fill: parent; visible: desk.lookActive
        maximumSpeechWidth: desk.sharedPanelWidth; speechFontSize: desk.sharedTextSize
        composerHeight: desk.composing ? composer.height : 0
        composerWidthFloor: desk.composerWidthFloor
        snapshot: desk.liveSnapshot; mascotSource: desk.mascotSource; darkMode: desk.darkMode
        headSource: desk.lookHeadSource; peekSource: desk.lookPeekSource
        idleSource: desk.lookIdleSource
        mascotWidth: desk.lookMascotWidth; mascotHeight: desk.lookMascotHeight; seatedOpticalHeight: desk.lookOpticalHeight
        errorSource: desk.lookErrorSource
        panelX: desk.panelX; panelY: desk.panelY; ratX: desk.ratX; ratY: desk.ratY
        placedBubbleWidth: desk.panelWidth
        placedBubbleHeight: desk.lookPlacedHeight
        maxBubbleHeight: desk.maxCornerSpeechHeight
        onMoveRequested: desk.moveRequested()
        onActivateRequested: desk.liveController.focusLook()
        onExpandRequested: desk.liveController.summonMinimal()
        onMenuRequested: (x, y) => moreMenu.popup(x, y)
        onSettingsRequested: desk.liveController.openLookSettings()
        onWorkbenchRequested: desk.liveController.openLookWorkbench()
        onSelectionRequested: (start, end) => desk.liveController.rememberLookSelection(start, end)
        onSelectionCopyRequested: text => desk.liveController.copyLookSelection(text)
        onCopyRequested: displayed => desk.liveController.copyLook(displayed)
        onDismissRequested: desk.liveController.dismissLookResult()
        onRetryRequested: desk.liveController.retryRequest()
        onCancelRequested: desk.liveController.cancel()
        onSelectionAccessRequested: desk.liveController.openSelectionAccess()
        onScrollRequested: offset => desk.liveController.rememberLookScroll(offset)
        onPendingRequested: desk.liveController.openPendingLook()
        onPreviewRequested: desk.liveController.previewPending()
        onReadingAnchorRequested: (text, position, delta) => desk.liveController.rememberReadingAnchor(text, position, delta)
        onOpenRequested: desk.liveController.openLook()
        onRecallRequested: desk.liveController.recallLookResult()
    }
    Shortcut { enabled: desk.lookActive && !desk.composing; context: Qt.ApplicationShortcut; sequences: [StandardKey.Paste]; onActivated: desk.liveController.pasteLook() }
    Shortcut { sequence: "Escape"; onActivated: { if (imageDialog.visible) imageDialog.close(); else if (folderDialog.visible) folderDialog.close(); else if (desk.lookActive) desk.liveController.dismissLookResult(); else desk.hideRequested() } }
    Shortcut { sequence: "Meta+W"; onActivated: desk.hideRequested() }
    Shortcut { sequence: "Meta+Q"; onActivated: desk.liveController.quit() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: desk.liveController.quit() }
    Shortcut { sequence: "Meta+,"; onActivated: desk.openSettings() }
    Menu {
        id: moreMenu
        // Qt 6.8+: the Look window can be just 122px wide. A separate popup
        // window keeps the secondary menu outside that tiny input mask.
        popupType: Popup.Window
        MenuItem { text: "Bôi đen chữ trong app nguồn → ⌥⇧Space"; enabled: false }
        MenuItem { text: "Xem lại công việc"; onTriggered: desk.liveController.summonLook() }
        MenuItem { text: "Viết yêu cầu"; onTriggered: desk.liveController.summonMinimal() }
        MenuItem { text: "Quyền đọc chữ bôi đen…"; onTriggered: desk.liveController.openSelectionAccess() }
        MenuItem { text: !desk.liveSnapshot.lookWatching ? "Bật theo dõi Clipboard" : desk.liveSnapshot.lookPaused ? "Tiếp tục Clipboard" : "Tạm dừng Clipboard"; onTriggered: desk.liveController.toggleLookPaused() }
        MenuItem { visible: desk.liveSnapshot.lookWatching; text: "Tắt theo dõi Clipboard"; onTriggered: desk.liveController.stopLook() }
        MenuItem { visible: desk.liveSnapshot.lookHasQueued; text: "Xem đoạn chờ"; onTriggered: desk.liveController.previewPending() }
        MenuItem { visible: desk.liveSnapshot.hasWorkbench; text: "Xem lại kết quả"; onTriggered: desk.liveController.recallLookResult() }
        MenuItem { enabled: !desk.liveSnapshot.busy; text: "Chọn vùng chữ để dịch…"; onTriggered: desk.liveController.captureRegion() }
        MenuItem { visible: desk.liveSnapshot.hasOcrSource; text: "Sửa chữ đã đọc…"; onTriggered: desk.navigate("ocr") }
        MenuItem { visible: Boolean(desk.liveSnapshot.imagePreviewUrl); text: "Xem ảnh nguồn…"; onTriggered: desk.navigate("image") }
        MenuItem { enabled: false; visible: Boolean(desk.liveSnapshot.hotkeyStatus); text: desk.liveSnapshot.hotkeyStatus || "" }
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
        id: imageDialog; title: "Chọn ảnh để dịch"; fileMode: FileDialog.OpenFile
        nameFilters: ["Ảnh (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"]
        onAccepted: desk.liveController.chooseImageFile(selectedFile, desk.draftText)
    }
}
