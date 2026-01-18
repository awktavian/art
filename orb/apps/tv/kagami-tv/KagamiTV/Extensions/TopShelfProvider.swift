//
// TopShelfProvider.swift -- Top Shelf Extension Support
//
// Kagami TV -- Top Shelf content provider for tvOS home screen
//
// Colony: Nexus (e4) -- Integration
//
// Features:
// - TVTopShelfContentProvider protocol implementation
// - Sectioned content for rooms and scenes
// - Dynamic content updates based on home state
// - Quick action inset content for scene activation
//
// Setup Instructions:
// 1. In Xcode, add new target: File > New > Target > TV Top Shelf Extension
// 2. Name it "KagamiTVTopShelf"
// 3. Move this file to the extension target
// 4. Add App Groups capability to both main app and extension
// 5. Configure shared UserDefaults suite for data passing
//
// h(x) >= 0. Always.
//

import Foundation
import TVServices

/// Top Shelf content provider for the Kagami tvOS app.
/// Displays rooms and scenes on the Apple TV home screen.
///
/// Note: This file should be moved to a TVTopShelfExtension target in Xcode.
/// The extension allows dynamic content on the Apple TV home screen when
/// the app is in the top row.
@available(tvOS 17.0, *)
class TopShelfProvider: TVTopShelfContentProvider {

    // MARK: - UserDefaults Keys (shared via App Groups)

    private let suiteName = "group.com.kagami.shared"
    private let roomsKey = "topshelf.rooms"
    private let scenesKey = "topshelf.scenes"

    // MARK: - TVTopShelfContentProvider

    /// Returns the top shelf content style.
    /// Using `.sectioned` for room/scene organization.
    var topShelfStyle: TVTopShelfContentStyle {
        return .sectioned
    }

    /// Provides the top shelf content items.
    func topShelfItems() async -> [TVTopShelfSectionedItem] {
        var sections: [TVTopShelfSectionedItem] = []

        // Quick Actions Section
        let quickActionsSection = createQuickActionsSection()
        sections.append(quickActionsSection)

        // Rooms Section (if available)
        if let roomsSection = await createRoomsSection() {
            sections.append(roomsSection)
        }

        // Scenes Section
        let scenesSection = createScenesSection()
        sections.append(scenesSection)

        return sections
    }

    // MARK: - Section Creation

    /// Creates the quick actions section with common home control actions.
    private func createQuickActionsSection() -> TVTopShelfSectionedItem {
        let section = TVTopShelfSectionedItem(identifier: "quick-actions")
        section.title = "Quick Actions"

        var items: [TVTopShelfItem] = []

        // All Lights Off
        let lightsOffItem = TVTopShelfSectionedItem(identifier: "action.lights_off")
        lightsOffItem.title = "All Lights Off"
        lightsOffItem.setImageURL(
            makeActionImageURL(icon: "lightbulb.slash.fill"),
            for: .screenScale1x
        )
        lightsOffItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://action/lights_off")!)
        items.append(lightsOffItem)

        // Movie Mode
        let movieItem = TVTopShelfSectionedItem(identifier: "action.movie_mode")
        movieItem.title = "Movie Mode"
        movieItem.setImageURL(
            makeActionImageURL(icon: "film.fill"),
            for: .screenScale1x
        )
        movieItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://scene/movie_mode")!)
        items.append(movieItem)

        // Goodnight
        let goodnightItem = TVTopShelfSectionedItem(identifier: "action.goodnight")
        goodnightItem.title = "Goodnight"
        goodnightItem.setImageURL(
            makeActionImageURL(icon: "moon.fill"),
            for: .screenScale1x
        )
        goodnightItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://scene/goodnight")!)
        items.append(goodnightItem)

        // Welcome Home
        let welcomeItem = TVTopShelfSectionedItem(identifier: "action.welcome_home")
        welcomeItem.title = "Welcome Home"
        welcomeItem.setImageURL(
            makeActionImageURL(icon: "house.fill"),
            for: .screenScale1x
        )
        welcomeItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://scene/welcome_home")!)
        items.append(welcomeItem)

        section.items = items
        return section
    }

    /// Creates the rooms section from cached room data.
    private func createRoomsSection() async -> TVTopShelfSectionedItem? {
        guard let rooms = loadCachedRooms(), !rooms.isEmpty else {
            return nil
        }

        let section = TVTopShelfSectionedItem(identifier: "rooms")
        section.title = "Rooms"

        var items: [TVTopShelfItem] = []

        for room in rooms.prefix(8) {  // Limit to 8 rooms
            let roomItem = TVTopShelfSectionedItem(identifier: "room.\(room.id)")
            roomItem.title = room.name
            roomItem.setImageURL(
                makeRoomImageURL(room: room),
                for: .screenScale1x
            )
            roomItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://room/\(room.id)")!)
            items.append(roomItem)
        }

        section.items = items
        return section
    }

    /// Creates the scenes section with predefined scenes.
    private func createScenesSection() -> TVTopShelfSectionedItem {
        let section = TVTopShelfSectionedItem(identifier: "scenes")
        section.title = "Scenes"

        let scenes: [(id: String, name: String, icon: String)] = [
            ("movie_mode", "Movie Mode", "film.fill"),
            ("goodnight", "Goodnight", "moon.zzz.fill"),
            ("welcome_home", "Welcome Home", "house.fill"),
            ("away", "Away Mode", "lock.fill"),
            ("focus", "Focus Mode", "target"),
            ("relax", "Relax", "flame.fill"),
            ("coffee", "Coffee Time", "cup.and.saucer.fill"),
            ("exit_movie_mode", "Exit Movie", "xmark.circle.fill"),
        ]

        var items: [TVTopShelfItem] = []

        for scene in scenes {
            let sceneItem = TVTopShelfSectionedItem(identifier: "scene.\(scene.id)")
            sceneItem.title = scene.name
            sceneItem.setImageURL(
                makeActionImageURL(icon: scene.icon),
                for: .screenScale1x
            )
            sceneItem.displayAction = TVTopShelfAction(url: URL(string: "kagami://scene/\(scene.id)")!)
            items.append(sceneItem)
        }

        section.items = items
        return section
    }

    // MARK: - Data Loading

    /// Room data structure for Top Shelf caching.
    private struct TopShelfRoom: Codable {
        let id: String
        let name: String
        let floor: String
        let lightLevel: Int
        let occupied: Bool
    }

    /// Loads cached room data from shared UserDefaults.
    private func loadCachedRooms() -> [TopShelfRoom]? {
        guard let defaults = UserDefaults(suiteName: suiteName),
              let data = defaults.data(forKey: roomsKey) else {
            return nil
        }

        return try? JSONDecoder().decode([TopShelfRoom].self, from: data)
    }

    // MARK: - Image URLs

    /// Creates a URL for action icons.
    /// In production, these would be actual image assets.
    private func makeActionImageURL(icon: String) -> URL? {
        // Use SF Symbols via a server endpoint or bundled assets
        // For now, return a placeholder
        return URL(string: "https://kagami.local/api/topshelf/icon/\(icon)")
    }

    /// Creates a URL for room preview images.
    private func makeRoomImageURL(room: TopShelfRoom) -> URL? {
        return URL(string: "https://kagami.local/api/topshelf/room/\(room.id)")
    }
}

// MARK: - Main App Integration

/// Call this from the main app to update Top Shelf content cache.
/// The Top Shelf extension reads from shared UserDefaults.
@available(tvOS 17.0, *)
struct TopShelfDataProvider {

    private static let suiteName = "group.com.kagami.shared"
    private static let roomsKey = "topshelf.rooms"

    /// Room data structure for Top Shelf caching.
    struct TopShelfRoom: Codable {
        let id: String
        let name: String
        let floor: String
        let lightLevel: Int
        let occupied: Bool
    }

    /// Updates the cached room data for Top Shelf.
    /// Call this after fetching rooms from the API.
    static func updateRoomsCache(rooms: [RoomModel]) {
        guard let defaults = UserDefaults(suiteName: suiteName) else {
            return
        }

        let topShelfRooms = rooms.map { room in
            TopShelfRoom(
                id: room.id,
                name: room.name,
                floor: room.floor,
                lightLevel: room.avgLightLevel,
                occupied: room.occupied
            )
        }

        if let data = try? JSONEncoder().encode(topShelfRooms) {
            defaults.set(data, forKey: roomsKey)
        }

        // Notify system to refresh Top Shelf
        TVTopShelfContentProvider.topShelfContentDidChange()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * Top Shelf puts Kagami on the home screen.
 * Quick access to scenes and rooms.
 * The smart home, always within reach.
 */
