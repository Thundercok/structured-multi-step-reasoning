// Availability-only diagnostic; never translates, downloads packs or prompts.
// Build: swiftc -target arm64-apple-macos14.0 this.swift -o /tmp/rat-translation-probe
import Foundation
import Translation

func emit(_ payload: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}

@available(macOS 15.0, *)
func probe() async {
    let availability = LanguageAvailability()
    let english = Locale.Language(identifier: "en")
    let vietnamese = Locale.Language(identifier: "vi")
    let pairStatus = await availability.status(from: english, to: vietnamese)
    let languages = await availability.supportedLanguages
    let installedSession: Bool
    if #available(macOS 26.0, *) { installedSession = true }
    else { installedSession = false }
    emit([
        "status": "observed",
        "framework_available": true,
        "installed_source_session_available": installedSession,
        "en_vi_status": String(describing: pairStatus),
        "supported_language_count": languages.count,
        "contains_vietnamese": languages.contains { $0.languageCode?.identifier == "vi" },
        "translation_performed": false,
        "packs_downloaded": false
    ])
    exit(0)
}

if #available(macOS 15.0, *) {
    Task { await probe() }
    dispatchMain()
} else {
    emit(["status": "unavailable", "reason": "requires_macos15_framework",
          "framework_available": false, "translation_performed": false,
          "packs_downloaded": false])
}
