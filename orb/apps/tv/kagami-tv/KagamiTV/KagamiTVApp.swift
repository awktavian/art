//
// KagamiTVApp.swift -- tvOS Application Entry Point
//
// Kagami TV -- Home automation on the big screen
//
// Colony: Nexus (e4) -- Integration
//
// h(x) >= 0. Always.
//

import SwiftUI

@main
struct KagamiTVApp: App {
    @StateObject private var appModel = TVAppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appModel)
                .preferredColorScheme(.dark)
                .task {
                    await appModel.connect()
                }
        }
    }
}

// MARK: - App Model

@MainActor
class TVAppModel: ObservableObject {
    @Published var isConnected = false
    @Published var safetyScore: Double?
    @Published var rooms: [RoomModel] = []
    @Published var isLoading = false
    @Published var error: String?

    /// Flag to show error alert
    @Published var showErrorAlert = false

    /// Current error for display
    @Published var currentError: KagamiAPIError?

    /// Offline queue status
    @Published var pendingActionsCount: Int = 0

    let apiService = KagamiAPIService.shared
    let offlineQueue = OfflineQueueService.shared
    let meshDiscovery = MeshDiscoveryService.shared

    init() {
        // Subscribe to offline queue changes
        offlineQueue.$pendingActions
            .map { $0.count }
            .assign(to: &$pendingActionsCount)
    }

    /// Connect to the server and fetch data using parallel initialization.
    func connect() async {
        isLoading = true
        error = nil

        // Start mesh discovery in parallel with API connection
        async let discoveryTask = meshDiscovery.startDiscovery()
        async let apiTask = initializeAPI()
        async let roomsTask = fetchRoomsAsync()

        // Await discovery first to potentially find local hub
        let discoveredURL = await discoveryTask
        if let url = discoveredURL {
            apiService.configure(baseURL: url)
        }

        // Then await API and rooms
        let (apiSuccess, fetchedRooms) = await (apiTask, roomsTask)

        // Update state from results
        isConnected = apiSuccess
        safetyScore = apiService.safetyScore
        rooms = fetchedRooms

        if !apiSuccess {
            if let apiError = apiService.lastError {
                currentError = apiError
                showErrorAlert = true
            }
        } else {
            currentError = nil
        }

        isLoading = false

        #if DEBUG
        print("[TVAppModel] Init complete - API: \(apiSuccess), Rooms: \(fetchedRooms.count)")
        #endif
    }

    /// Initialize API connection (for parallel init)
    private func initializeAPI() async -> Bool {
        await apiService.connect()
        return apiService.isConnected
    }

    /// Fetch rooms asynchronously (for parallel init)
    private func fetchRoomsAsync() async -> [RoomModel] {
        do {
            return try await apiService.fetchRooms()
        } catch {
            self.error = error.localizedDescription
            return []
        }
    }

    /// Refresh all data from the server
    func refresh() async {
        await connect()
    }

    /// Clear the current error
    func clearError() {
        currentError = nil
        showErrorAlert = false
        error = nil
    }

    /// Retry the last failed operation
    func retryLastOperation() async {
        apiService.resetCircuitBreaker()
        await connect()
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let kagamiDidLogout = Notification.Name("kagamiDidLogout")
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
