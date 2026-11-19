// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "ReceiptyPhotosHelper",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "ReceiptyPhotosHelper",
            linkerSettings: [
                .linkedFramework("Photos"),
                .linkedFramework("AppKit"),
            ]
        )
    ]
)

