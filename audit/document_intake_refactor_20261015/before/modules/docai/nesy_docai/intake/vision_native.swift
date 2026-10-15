import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    print("[]")
    exit(0)
}

let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]")
    exit(0)
}

let request = VNRecognizeTextRequest { request, error in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        print("[]")
        return
    }
    
    var results: [[String: Any]] = []
    let width = CGFloat(cgImage.width)
    let height = CGFloat(cgImage.height)

    for observation in observations {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let bbox = observation.boundingBox
        
        // Convert normalized coordinates (Vision Y is bottom-up) to top-down pixels
        let pxX = Int(bbox.origin.x * width)
        let pxY = Int((1.0 - bbox.origin.y - bbox.size.height) * height)
        let pxW = Int(bbox.size.width * width)
        let pxH = Int(bbox.size.height * height)

        let item: [String: Any] = [
            "text": candidate.string,
            "confidence": candidate.confidence,
            "bbox": [pxX, pxY, pxX + pxW, pxY + pxH]
        ]
        results.append(item)
    }
    
    if let jsonData = try? JSONSerialization.data(withJSONObject: results, options: []),
       let jsonString = String(data: jsonData, encoding: .utf8) {
        print(jsonString)
    } else {
        print("[]")
    }
}

request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])
