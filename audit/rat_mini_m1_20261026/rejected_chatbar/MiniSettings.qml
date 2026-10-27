import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: settingsDialog
    property var controller: null
    property var config: controller ? controller.settings : ({})
    title: "RAT Mini · Cài đặt"
    modal: true
    width: Math.min(560, desk.width - 28)
    height: Math.min(600, desk.height - 20)
    anchors.centerIn: parent
    palette.window: desk.paperColor
    palette.windowText: desk.ink
    palette.text: desk.ink
    palette.base: desk.inputColor
    onOpened: {
        roots.text = (config.roots || []).join("\n")
        provider.currentIndex = Math.max(0, ["openai", "deepseek", "groq"].indexOf(config.provider))
        model.text = config.model || "gpt-4.1-mini"
        translation.currentIndex = Math.max(0,["apple","llm","deepl","google","mymemory"].indexOf(config.translation_provider))
        semantic.checked = Boolean(config.semantic_enabled)
        fallback.checked = Boolean(config.free_fallback)
        target.currentIndex = Math.max(0,["vi","en","ja","ko","zh","fr","de"].indexOf(config.target_language))
        source.currentIndex = Math.max(0,["auto","vi","en","ja","ko","zh","fr","de"].indexOf(config.source_language || "auto"))
        secret.text = ""
    }
    contentItem: ScrollView {
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: 10
            Label { text: "Thư mục được phép tìm · mỗi dòng một đường dẫn"; color: desk.ink; wrapMode: Text.Wrap; Layout.fillWidth: true }
            TextArea {
                id: roots; objectName: "miniRoots"; Layout.fillWidth: true; Layout.preferredHeight: 80
                placeholderText: "/Users/tên-bạn/Documents\n/Users/tên-bạn/Downloads"
                wrapMode: TextEdit.Wrap; selectByMouse: true
                Accessible.name: "Thư mục tìm kiếm, mỗi dòng một đường dẫn"
            }
            CheckBox { id: semantic; text: "Bật tìm ngữ nghĩa local · model 135MB" }
            Label { text: "TXT, Markdown, PDF có text. Chỉ mục cập nhật thủ công khi bấm Lập chỉ mục."; wrapMode: Text.Wrap; color: desk.muted; Layout.fillWidth: true }
            GridLayout {
                columns: 2; Layout.fillWidth: true
                Label { text: "Agent cloud" }
                ComboBox { id: provider; objectName: "miniProvider"; model: ["OpenAI","DeepSeek","Groq"]; Layout.fillWidth: true }
                Label { text: "Model ID" }
                TextField { id: model; objectName: "miniModel"; Layout.fillWidth: true; selectByMouse: true }
                Label { text: "Backend dịch" }
                ComboBox { id: translation; objectName: "miniTranslationProvider"; model: ["Apple nếu sẵn sàng","LLM cloud","DeepL API","Google Cloud Translation","MyMemory"]; Layout.fillWidth: true }
                Label { text: "Ngôn ngữ nguồn" }
                ComboBox { id: source; objectName: "miniSourceLanguage"; model: ["Tự nhận diện","Tiếng Việt","English","日本語","한국어","中文","Français","Deutsch"]; Layout.fillWidth: true }
                Label { text: "Dịch sang" }
                ComboBox { id: target; objectName: "miniTargetLanguage"; model: ["Tiếng Việt","English","日本語","한국어","中文","Français","Deutsch"]; Layout.fillWidth: true }
                Label { text: "Lưu key cho" }
                ComboBox { id: keyProvider; model: ["openai","deepseek","groq","deepl","google"]; Layout.fillWidth: true }
                Label { text: "API key" }
                TextField { id: secret; objectName: "miniApiKey"; echoMode: TextInput.Password; placeholderText: "Để trống để giữ key cũ"; Layout.fillWidth: true; selectByMouse: true }
            }
            CheckBox { id: fallback; objectName: "miniFreeFallback"; text: "Cho phép MyMemory (gửi đoạn cần dịch online)" }
            Label {
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: desk.muted
                text: "Key lưu trong macOS Keychain. Agent nhận yêu cầu và metadata tên file, không nhận toàn bộ chỉ mục. Backend dịch nhận đoạn bạn yêu cầu dịch."
            }
            Label { visible: Boolean(desk.liveSnapshot.errorText); text: desk.liveSnapshot.errorText || ""; wrapMode: Text.Wrap; color: "#a14636"; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Button {
                    text: "Lập chỉ mục"; enabled: !desk.liveSnapshot.busy && Boolean(settingsDialog.config.semantic_enabled)
                    onClicked: { settingsDialog.close(); settingsDialog.controller.indexFiles() }
                }
                Item { Layout.fillWidth: true }
                Button { text: "Đóng"; onClicked: settingsDialog.close() }
                Button {
                    text: "Lưu"; objectName: "miniSaveSettings"
                    onClicked: {
                        const okay = settingsDialog.controller.configure({
                            roots: roots.text.split("\n").map(p => p.trim()).filter(p => p.length > 0),
                            provider: ["openai","deepseek","groq"][provider.currentIndex], model: model.text.trim(),
                            translation_provider: ["apple","llm","deepl","google","mymemory"][translation.currentIndex],
                            source_language: ["auto","vi","en","ja","ko","zh","fr","de"][source.currentIndex],
                            target_language: ["vi","en","ja","ko","zh","fr","de"][target.currentIndex],
                            semantic_enabled: semantic.checked, free_fallback: fallback.checked,
                            key_provider: keyProvider.currentText, api_key: secret.text
                        })
                        secret.text = ""
                        if (okay) settingsDialog.close()
                    }
                }
            }
        }
    }
}
