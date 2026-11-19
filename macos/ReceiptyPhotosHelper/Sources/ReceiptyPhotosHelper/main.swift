import AppKit
import Foundation
import Photos

struct HelperError: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

final class ResultBox<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Value
    init(_ value: Value) { self.value = value }
    func set(_ newValue: Value) { lock.lock(); value = newValue; lock.unlock() }
    func get() -> Value { lock.lock(); defer { lock.unlock() }; return value }
}

func statusName(_ status: PHAuthorizationStatus) -> String {
    switch status {
    case .notDetermined: return "notDetermined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    case .limited: return "limited"
    @unknown default: return "unknown"
    }
}

func requireAuthorization() throws {
    let status = PHPhotoLibrary.authorizationStatus(for: .readWrite)
    guard status == .authorized || status == .limited else {
        throw HelperError("Photos access is \(statusName(status))")
    }
}

func assetDictionary(_ asset: PHAsset) -> [String: Any] {
    let resources = PHAssetResource.assetResources(for: asset)
    let filename = resources.first?.originalFilename ?? asset.localIdentifier
    let formatter = ISO8601DateFormatter()
    var result: [String: Any] = [
        "id": asset.localIdentifier,
        "filename": filename,
        "mediaType": asset.mediaType == .video ? "video" : "image",
        "pixelWidth": asset.pixelWidth,
        "pixelHeight": asset.pixelHeight,
        "favorite": asset.isFavorite,
    ]
    if let date = asset.creationDate {
        result["creationDate"] = formatter.string(from: date)
        result["creationYear"] = Calendar.current.component(.year, from: date)
    }
    return result
}

func fetchAsset(_ identifier: String) throws -> PHAsset {
    try requireAuthorization()
    let result = PHAsset.fetchAssets(withLocalIdentifiers: [identifier], options: nil)
    guard let asset = result.firstObject else { throw HelperError("Photos asset not found") }
    return asset
}

func albums() throws -> [[String: Any]] {
    try requireAuthorization()
    var output: [[String: Any]] = []
    let userAlbums = PHAssetCollection.fetchAssetCollections(
        with: .album, subtype: .any, options: nil
    )
    userAlbums.enumerateObjects { collection, _, _ in
        output.append([
            "id": collection.localIdentifier,
            "title": collection.localizedTitle ?? "Untitled album",
            "count": PHAsset.fetchAssets(in: collection, options: nil).count,
        ])
    }
    return output.sorted { ($0["title"] as? String ?? "") < ($1["title"] as? String ?? "") }
}

func assets(albumId: String?) throws -> [[String: Any]] {
    try requireAuthorization()
    let result: PHFetchResult<PHAsset>
    if let albumId {
        let collections = PHAssetCollection.fetchAssetCollections(
            withLocalIdentifiers: [albumId], options: nil
        )
        guard let collection = collections.firstObject else {
            throw HelperError("Photos album not found")
        }
        result = PHAsset.fetchAssets(in: collection, options: nil)
    } else {
        result = PHAsset.fetchAssets(with: nil)
    }
    var output: [[String: Any]] = []
    result.enumerateObjects { asset, _, _ in output.append(assetDictionary(asset)) }
    return output
}

func exportAsset(_ identifier: String, destination: String) throws -> [String: Any] {
    let asset = try fetchAsset(identifier)
    guard let resource = PHAssetResource.assetResources(for: asset).first else {
        throw HelperError("Photos asset has no exportable resource")
    }
    let destinationURL = URL(fileURLWithPath: destination)
    try FileManager.default.createDirectory(
        at: destinationURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    let options = PHAssetResourceRequestOptions()
    options.isNetworkAccessAllowed = true
    let semaphore = DispatchSemaphore(value: 0)
    let exportError = ResultBox<Error?>(nil)
    PHAssetResourceManager.default().writeData(
        for: resource, toFile: destinationURL, options: options
    ) { error in
        exportError.set(error)
        semaphore.signal()
    }
    semaphore.wait()
    if let error = exportError.get() { throw error }
    return ["destination": destination, "asset": assetDictionary(asset)]
}

func handle(_ request: [String: Any]) throws -> Any {
    guard let command = request["command"] as? String else {
        throw HelperError("Missing command")
    }
    let arguments = request["arguments"] as? [String: Any] ?? [:]
    switch command {
    case "authorization":
        return ["status": statusName(PHPhotoLibrary.authorizationStatus(for: .readWrite))]
    case "requestAuthorization":
        let semaphore = DispatchSemaphore(value: 0)
        let result = ResultBox(PHAuthorizationStatus.notDetermined)
        PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
            result.set(status)
            semaphore.signal()
        }
        semaphore.wait()
        return ["status": statusName(result.get())]
    case "listAlbums":
        return try albums()
    case "listAssets":
        return try assets(albumId: arguments["albumId"] as? String)
    case "getAsset":
        guard let identifier = arguments["assetId"] as? String else {
            throw HelperError("Missing assetId")
        }
        return assetDictionary(try fetchAsset(identifier))
    case "exportAsset":
        guard let identifier = arguments["assetId"] as? String,
              let destination = arguments["destination"] as? String else {
            throw HelperError("Missing assetId or destination")
        }
        return try exportAsset(identifier, destination: destination)
    default:
        throw HelperError("Unknown command: \(command)")
    }
}

func respond(_ object: [String: Any]) {
    do {
        let data = try JSONSerialization.data(withJSONObject: object)
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    } catch {
        FileHandle.standardError.write(Data("Unable to encode response: \(error)\n".utf8))
        exit(2)
    }
}

guard let line = readLine(), let data = line.data(using: .utf8) else {
    respond(["ok": false, "error": "Expected one JSON request on stdin"])
    exit(1)
}

do {
    guard let request = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        throw HelperError("Request must be a JSON object")
    }
    respond(["ok": true, "result": try handle(request)])
} catch {
    respond(["ok": false, "error": String(describing: error)])
    exit(1)
}

