//
// SearchView.swift — Unified Search for Rooms, Scenes, and Settings
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Unified search across rooms, scenes, and settings
//   - Typeahead with instant filtering
//   - Quick actions from search results
//   - Recent searches
//
// h(x) >= 0. Always.
//

import SwiftUI
import KagamiDesign

// MARK: - Search Result Types

enum SearchResultType: String, CaseIterable {
    case room = "room"
    case scene = "scene"
    case setting = "setting"
    case action = "action"

    var icon: String {
        switch self {
        case .room: return "square.grid.2x2"
        case .scene: return "sparkles"
        case .setting: return "gear"
        case .action: return "bolt.fill"
        }
    }

    var color: Color {
        switch self {
        case .room: return .grove
        case .scene: return .forge
        case .setting: return .beacon
        case .action: return .crystal
        }
    }
}

struct SearchResult: Identifiable, Hashable {
    let id: String
    let title: String
    let subtitle: String
    let type: SearchResultType
    let action: SearchResultAction

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: SearchResult, rhs: SearchResult) -> Bool {
        lhs.id == rhs.id
    }
}

enum SearchResultAction {
    case navigateToRoom(String)
    case executeScene(String)
    case openSetting(String)
    case executeAction(String)
}

// MARK: - Search View Model

@MainActor
class SearchViewModel: ObservableObject {
    @Published var searchText: String = ""
    @Published var results: [SearchResult] = []
    @Published var recentSearches: [String] = []
    @Published var isSearching: Bool = false

    private let maxRecentSearches = 5

    init() {
        loadRecentSearches()
    }

    // MARK: - Search Logic

    /// Static demo rooms for search
    private let demoRooms: [(id: String, name: String, floor: String)] = [
        ("living_room", "Living Room", "Main Floor"),
        ("primary_bedroom", "Primary Bedroom", "Upper Floor"),
        ("office", "Office", "Main Floor"),
        ("kitchen", "Kitchen", "Main Floor"),
        ("dining_room", "Dining Room", "Main Floor"),
        ("media_room", "Media Room", "Lower Floor"),
        ("guest_bedroom", "Guest Bedroom", "Upper Floor"),
        ("bathroom_primary", "Primary Bathroom", "Upper Floor"),
        ("garage", "Garage", "Main Floor"),
        ("patio", "Patio", "Main Floor")
    ]

    func search(_ query: String) {
        guard !query.isEmpty else {
            results = []
            return
        }

        isSearching = true
        let lowercasedQuery = query.lowercased()
        var searchResults: [SearchResult] = []

        // Search Rooms
        for room in demoRooms where room.name.lowercased().contains(lowercasedQuery) {
            searchResults.append(SearchResult(
                id: "room_\(room.id)",
                title: room.name,
                subtitle: room.floor,
                type: .room,
                action: .navigateToRoom(room.id)
            ))
        }

        // Search Scenes
        let scenes = [
            ("movie_mode", "Movie Mode", "Dim lights, lower TV, close shades"),
            ("goodnight", "Goodnight", "All lights off, lock doors"),
            ("welcome_home", "Welcome Home", "Warm lights, open shades"),
            ("away", "Away Mode", "Secure house, reduce energy"),
            ("focus", "Focus Mode", "Bright lights, open shades"),
            ("relax", "Relax", "Dim lights, fireplace on"),
            ("good_morning", "Good Morning", "Open shades, raise lights")
        ]

        for (id, name, description) in scenes where name.lowercased().contains(lowercasedQuery) {
            searchResults.append(SearchResult(
                id: "scene_\(id)",
                title: name,
                subtitle: description,
                type: .scene,
                action: .executeScene(id)
            ))
        }

        // Search Settings
        let settings = [
            ("server", "Server Settings", "Configure Kagami server"),
            ("account", "Account", "Manage your account"),
            ("notifications", "Notifications", "Notification preferences"),
            ("language", "Language", "Change app language"),
            ("accessibility", "Accessibility", "Accessibility options"),
            ("about", "About", "App version and info")
        ]

        for (id, name, description) in settings where name.lowercased().contains(lowercasedQuery) {
            searchResults.append(SearchResult(
                id: "setting_\(id)",
                title: name,
                subtitle: description,
                type: .setting,
                action: .openSetting(id)
            ))
        }

        // Search Quick Actions
        let actions = [
            ("lights_on", "Lights On", "Turn all lights on"),
            ("lights_off", "Lights Off", "Turn all lights off"),
            ("fireplace_on", "Fireplace On", "Turn on fireplace"),
            ("shades_open", "Open Shades", "Open all shades"),
            ("shades_close", "Close Shades", "Close all shades"),
            ("lock_all", "Lock All Doors", "Lock all doors")
        ]

        for (id, name, description) in actions where name.lowercased().contains(lowercasedQuery) {
            searchResults.append(SearchResult(
                id: "action_\(id)",
                title: name,
                subtitle: description,
                type: .action,
                action: .executeAction(id)
            ))
        }

        results = searchResults
        isSearching = false
    }

    func addRecentSearch(_ query: String) {
        guard !query.isEmpty else { return }

        // Remove if already exists
        recentSearches.removeAll { $0 == query }

        // Add to front
        recentSearches.insert(query, at: 0)

        // Limit to max
        if recentSearches.count > maxRecentSearches {
            recentSearches = Array(recentSearches.prefix(maxRecentSearches))
        }

        saveRecentSearches()
    }

    func clearRecentSearches() {
        recentSearches = []
        saveRecentSearches()
    }

    private func loadRecentSearches() {
        recentSearches = UserDefaults.standard.stringArray(forKey: "recentSearches") ?? []
    }

    private func saveRecentSearches() {
        UserDefaults.standard.set(recentSearches, forKey: "recentSearches")
    }

    // MARK: - Execute Actions

    func executeResult(_ result: SearchResult) async {
        addRecentSearch(result.title)

        switch result.action {
        case .navigateToRoom(let roomId):
            // Post notification for room navigation
            NotificationCenter.default.post(
                name: .kagamiNavigateToRoom,
                object: nil,
                userInfo: ["roomId": roomId]
            )

        case .executeScene(let sceneId):
            await KagamiAPIService.shared.executeScene(sceneId)
            UINotificationFeedbackGenerator().notificationOccurred(.success)

        case .openSetting(let settingId):
            // Post notification for settings navigation
            NotificationCenter.default.post(
                name: .kagamiNavigateToSetting,
                object: nil,
                userInfo: ["settingId": settingId]
            )

        case .executeAction(let actionId):
            await executeQuickAction(actionId)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
    }

    private func executeQuickAction(_ actionId: String) async {
        switch actionId {
        case "lights_on":
            await KagamiAPIService.shared.setLights(100)
        case "lights_off":
            await KagamiAPIService.shared.setLights(0)
        case "fireplace_on":
            await KagamiAPIService.shared.toggleFireplace(on: true)
        case "shades_open":
            await KagamiAPIService.shared.controlShades("open")
        case "shades_close":
            await KagamiAPIService.shared.controlShades("close")
        case "lock_all":
            await KagamiAPIService.shared.lockAll()
        default:
            break
        }
    }
}

// MARK: - Search Bar View

struct KagamiSearchBar: View {
    @Binding var text: String
    let placeholder: String
    var onSubmit: (() -> Void)?

    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: KagamiSpacing.sm) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.accessibleTextSecondary)
                .accessibilityHidden(true)

            TextField(placeholder, text: $text)
                .font(KagamiFont.body())
                .foregroundColor(.accessibleTextPrimary)
                .autocapitalization(.none)
                .disableAutocorrection(true)
                .focused($isFocused)
                .onSubmit {
                    onSubmit?()
                }
                .accessibilityLabel("Search")
                .accessibilityHint("Enter text to search rooms, scenes, and settings")

            if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.accessibleTextTertiary)
                }
                .accessibilityLabel("Clear search")
            }
        }
        .padding(.horizontal, KagamiSpacing.md)
        .padding(.vertical, KagamiSpacing.sm)
        .background(Color.voidLight)
        .cornerRadius(KagamiRadius.md)
        .accessibilityIdentifier(AccessibilityIdentifiers.Search.searchBar)
    }
}

// MARK: - Search View

struct SearchView: View {
    @StateObject private var viewModel = SearchViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search Bar
                KagamiSearchBar(
                    text: $viewModel.searchText,
                    placeholder: "Search rooms, scenes, settings..."
                )
                .padding()
                .onChange(of: viewModel.searchText) { _, newValue in
                    viewModel.search(newValue)
                }

                // Results or Recent Searches
                if viewModel.searchText.isEmpty {
                    recentSearchesView
                } else if viewModel.results.isEmpty && !viewModel.isSearching {
                    noResultsView
                } else {
                    searchResultsView
                }

                Spacer()
            }
            .background(Color.void)
            .navigationTitle("Search")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(.crystal)
                }
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Search.view)
    }

    // MARK: - Recent Searches

    private var recentSearchesView: some View {
        VStack(alignment: .leading, spacing: KagamiSpacing.md) {
            if !viewModel.recentSearches.isEmpty {
                HStack {
                    Text("Recent Searches")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                    Spacer()
                    Button("Clear") {
                        viewModel.clearRecentSearches()
                    }
                    .font(KagamiFont.caption())
                    .foregroundColor(.crystal)
                }
                .padding(.horizontal)

                ForEach(viewModel.recentSearches, id: \.self) { search in
                    Button {
                        viewModel.searchText = search
                        viewModel.search(search)
                    } label: {
                        HStack {
                            Image(systemName: "clock.arrow.circlepath")
                                .foregroundColor(.accessibleTextTertiary)
                            Text(search)
                                .font(KagamiFont.body())
                                .foregroundColor(.accessibleTextPrimary)
                            Spacer()
                        }
                        .padding(.horizontal)
                        .padding(.vertical, KagamiSpacing.sm)
                    }
                }
            } else {
                VStack(spacing: KagamiSpacing.md) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 48))
                        .foregroundColor(.accessibleTextTertiary)

                    Text("Search for rooms, scenes, or settings")
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextSecondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 60)
            }
        }
        .padding(.top)
    }

    // MARK: - No Results

    private var noResultsView: some View {
        VStack(spacing: KagamiSpacing.md) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.accessibleTextTertiary)

            Text("No results for \"\(viewModel.searchText)\"")
                .font(KagamiFont.body())
                .foregroundColor(.accessibleTextSecondary)

            Text("Try searching for rooms, scenes, or settings")
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 60)
        .accessibilityIdentifier(AccessibilityIdentifiers.Search.noResults)
    }

    // MARK: - Search Results

    private var searchResultsView: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                // Group by type
                let groupedResults = Dictionary(grouping: viewModel.results) { $0.type }

                ForEach(SearchResultType.allCases, id: \.self) { type in
                    if let results = groupedResults[type], !results.isEmpty {
                        SearchResultSection(
                            type: type,
                            results: results,
                            onSelect: { result in
                                Task {
                                    await viewModel.executeResult(result)
                                    dismiss()
                                }
                            }
                        )
                    }
                }
            }
        }
        .accessibilityIdentifier(AccessibilityIdentifiers.Search.resultsList)
    }
}

// MARK: - Search Result Section

struct SearchResultSection: View {
    let type: SearchResultType
    let results: [SearchResult]
    let onSelect: (SearchResult) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Section Header
            HStack {
                Image(systemName: type.icon)
                    .foregroundColor(type.color)
                Text(sectionTitle)
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextSecondary)
            }
            .padding(.horizontal)
            .padding(.vertical, KagamiSpacing.sm)

            // Results
            ForEach(results) { result in
                SearchResultRow(result: result, onSelect: onSelect)
            }
        }
    }

    private var sectionTitle: String {
        switch type {
        case .room: return "Rooms"
        case .scene: return "Scenes"
        case .setting: return "Settings"
        case .action: return "Quick Actions"
        }
    }
}

// MARK: - Search Result Row

struct SearchResultRow: View {
    let result: SearchResult
    let onSelect: (SearchResult) -> Void

    var body: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            onSelect(result)
        } label: {
            HStack(spacing: KagamiSpacing.md) {
                // Icon
                ZStack {
                    Circle()
                        .fill(result.type.color.opacity(0.2))
                        .frame(width: 40, height: 40)

                    Image(systemName: result.type.icon)
                        .foregroundColor(result.type.color)
                }

                // Content
                VStack(alignment: .leading, spacing: 2) {
                    Text(result.title)
                        .font(KagamiFont.body(weight: .medium))
                        .foregroundColor(.accessibleTextPrimary)

                    Text(result.subtitle)
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                        .lineLimit(1)
                }

                Spacer()

                // Action indicator
                Image(systemName: actionIcon)
                    .foregroundColor(.accessibleTextTertiary)
                    .font(.caption)
            }
            .padding(.horizontal)
            .padding(.vertical, KagamiSpacing.sm)
            .frame(minHeight: 44) // Minimum touch target
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(result.title). \(result.subtitle)")
        .accessibilityHint(accessibilityHint)
    }

    private var actionIcon: String {
        switch result.action {
        case .navigateToRoom: return "chevron.right"
        case .executeScene: return "play.fill"
        case .openSetting: return "chevron.right"
        case .executeAction: return "bolt.fill"
        }
    }

    private var accessibilityHint: String {
        switch result.action {
        case .navigateToRoom: return "Double tap to view room"
        case .executeScene: return "Double tap to activate scene"
        case .openSetting: return "Double tap to open setting"
        case .executeAction: return "Double tap to execute action"
        }
    }
}

// MARK: - Accessibility Identifiers

extension AccessibilityIdentifiers {
    enum Search {
        static let view = "search.view"
        static let searchBar = "search.searchBar"
        static let resultsList = "search.results"
        static let noResults = "search.noResults"

        static func result(_ id: String) -> String {
            "search.result.\(id)"
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let kagamiNavigateToRoom = Notification.Name("kagamiNavigateToRoom")
    static let kagamiNavigateToSetting = Notification.Name("kagamiNavigateToSetting")
}

// MARK: - Search Button Modifier

/// View modifier to add a search button to navigation bar
struct SearchButtonModifier: ViewModifier {
    @State private var showSearch = false

    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        showSearch = true
                    } label: {
                        Image(systemName: "magnifyingglass")
                    }
                    .accessibilityLabel("Search")
                    .accessibilityHint("Open search to find rooms, scenes, and settings")
                }
            }
            .sheet(isPresented: $showSearch) {
                SearchView()
            }
    }
}

extension View {
    /// Add a search button to the navigation bar
    func withSearchButton() -> some View {
        modifier(SearchButtonModifier())
    }
}

/*
 * Mirror
 * Search unifies the experience.
 * Find anything in 2 taps.
 * h(x) >= 0. Always.
 */
