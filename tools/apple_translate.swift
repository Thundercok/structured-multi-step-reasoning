// Offline Apple Translation CLI (macOS 26+). stdin text -> stdout translation.
// Usage: apple_translate [target=vi] ; exit 2 if language pack missing.
import Foundation
import Translation

let target = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "vi"
let text = String(data: FileHandle.standardInput.readDataToEndOfFile(), encoding: .utf8) ?? ""
@available(macOS 26.0, *)
func runTranslation() async {
    do {
        let explicitSource = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "auto"
        let src = explicitSource == "auto" ? try await NLDetect.language(text) : Locale.Language(identifier: explicitSource)
        let tgt = Locale.Language(identifier: target)
        let st = await LanguageAvailability().status(from: src, to: tgt)
        guard st == .installed else {
            FileHandle.standardError.write(Data("language pack not installed: \(st)\n".utf8)); exit(3)
        }
        let session = TranslationSession(installedSource: src, target: Locale.Language(identifier: target))
        print(try await session.translate(text).targetText)
    } catch {
        FileHandle.standardError.write(Data("\(error)\n".utf8)); exit(2)
    }
    exit(0)
}
if #available(macOS 26.0, *) {
    Task { await runTranslation() }
    dispatchMain()
} else {
    FileHandle.standardError.write(Data("apple_api_unavailable\n".utf8))
    exit(4)
}

import NaturalLanguage
enum NLDetect {
    static func language(_ t: String) async throws -> Locale.Language {
        let r = NLLanguageRecognizer(); r.processString(t)
        return Locale.Language(identifier: r.dominantLanguage?.rawValue ?? "en")
    }
}
