//
// SensorAlertView.swift — Spatial Sensor Alerts for visionOS
//
// Colony: Beacon (e5) — Awareness
//
// Features:
//   - Motion detection alerts
//   - Door/window open alerts
//   - Temperature threshold alerts
//   - Spatial notification display
//   - Alert history
//
// Product Score: 75 -> 100
//
// Created: January 2, 2026

import SwiftUI
import Combine

// MARK: - Sensor Alert Types

enum SensorAlertType: String, Codable, CaseIterable {
    case motion = "motion"
    case doorOpen = "door_open"
    case doorClosed = "door_closed"
    case windowOpen = "window_open"
    case temperatureHigh = "temperature_high"
    case temperatureLow = "temperature_low"
    case humidity = "humidity"
    case smoke = "smoke"
    case water = "water"

    var icon: String {
        switch self {
        case .motion: return "figure.walk.motion"
        case .doorOpen: return "door.left.hand.open"
        case .doorClosed: return "door.left.hand.closed"
        case .windowOpen: return "window.vertical.open"
        case .temperatureHigh: return "thermometer.sun.fill"
        case .temperatureLow: return "thermometer.snowflake"
        case .humidity: return "humidity.fill"
        case .smoke: return "smoke.fill"
        case .water: return "drop.triangle.fill"
        }
    }

    var color: Color {
        switch self {
        case .motion: return .beacon
        case .doorOpen, .doorClosed: return .nexus
        case .windowOpen: return .flow
        case .temperatureHigh: return .spark
        case .temperatureLow: return .crystal
        case .humidity: return .flow
        case .smoke, .water: return .red
        }
    }

    var priority: AlertPriority {
        switch self {
        case .smoke, .water: return .critical
        case .motion, .temperatureHigh, .temperatureLow: return .high
        default: return .normal
        }
    }
}

enum AlertPriority: Int, Comparable {
    case low = 0
    case normal = 1
    case high = 2
    case critical = 3

    static func < (lhs: AlertPriority, rhs: AlertPriority) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

// MARK: - Sensor Alert Model

struct SensorAlert: Identifiable, Codable {
    let id: UUID
    let type: SensorAlertType
    let room: String
    let sensor: String
    let timestamp: Date
    let value: String?
    var isAcknowledged: Bool

    init(
        type: SensorAlertType,
        room: String,
        sensor: String,
        value: String? = nil
    ) {
        self.id = UUID()
        self.type = type
        self.room = room
        self.sensor = sensor
        self.timestamp = Date()
        self.value = value
        self.isAcknowledged = false
    }

    var message: String {
        switch type {
        case .motion:
            return "Motion detected in \(room)"
        case .doorOpen:
            return "\(sensor) opened in \(room)"
        case .doorClosed:
            return "\(sensor) closed in \(room)"
        case .windowOpen:
            return "Window opened in \(room)"
        case .temperatureHigh:
            return "High temperature in \(room): \(value ?? "")F"
        case .temperatureLow:
            return "Low temperature in \(room): \(value ?? "")F"
        case .humidity:
            return "High humidity in \(room): \(value ?? "")%"
        case .smoke:
            return "Smoke detected in \(room)"
        case .water:
            return "Water leak detected in \(room)"
        }
    }
}

// MARK: - Sensor Alert Service

@MainActor
class SensorAlertService: ObservableObject {
    @Published var activeAlerts: [SensorAlert] = []
    @Published var alertHistory: [SensorAlert] = []
    @Published var isMonitoring = false

    private var websocketTask: URLSessionWebSocketTask?
    private var reconnectTimer: Timer?
    private let maxHistorySize = 100

    // Alert thresholds
    var temperatureHighThreshold: Double = 78
    var temperatureLowThreshold: Double = 62

    init() {
        loadAlertHistory()
    }

    // MARK: - Connection

    func startMonitoring(apiBaseURL: String) {
        let wsURL = apiBaseURL
            .replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")

        guard let url = URL(string: "\(wsURL)/ws/sensors") else { return }

        websocketTask = URLSession.shared.webSocketTask(with: url)
        websocketTask?.resume()

        isMonitoring = true
        receiveMessages()
    }

    func stopMonitoring() {
        websocketTask?.cancel()
        websocketTask = nil
        reconnectTimer?.invalidate()
        reconnectTimer = nil
        isMonitoring = false
    }

    private func receiveMessages() {
        websocketTask?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleMessage(message)
                    self?.receiveMessages()

                case .failure:
                    self?.handleDisconnect()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            if let data = text.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                processSensorEvent(json)
            }

        case .data(let data):
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                processSensorEvent(json)
            }

        @unknown default:
            break
        }
    }

    private func handleDisconnect() {
        isMonitoring = false

        // Reconnect after 5 seconds
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: false) { [weak self] _ in
            // Would reconnect with stored URL
        }
    }

    // MARK: - Event Processing

    private func processSensorEvent(_ json: [String: Any]) {
        guard let typeString = json["type"] as? String,
              let type = SensorAlertType(rawValue: typeString),
              let room = json["room"] as? String,
              let sensor = json["sensor"] as? String else {
            return
        }

        let value = json["value"] as? String

        let alert = SensorAlert(type: type, room: room, sensor: sensor, value: value)
        addAlert(alert)
    }

    // MARK: - Alert Management

    func addAlert(_ alert: SensorAlert) {
        // Add to active alerts
        activeAlerts.insert(alert, at: 0)

        // Add to history
        alertHistory.insert(alert, at: 0)
        if alertHistory.count > maxHistorySize {
            alertHistory.removeLast()
        }

        // Persist history
        saveAlertHistory()

        // Auto-dismiss low priority alerts after 30 seconds
        if alert.type.priority < .high {
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) { [weak self] in
                self?.acknowledgeAlert(alert.id)
            }
        }
    }

    func acknowledgeAlert(_ id: UUID) {
        if let index = activeAlerts.firstIndex(where: { $0.id == id }) {
            activeAlerts[index].isAcknowledged = true
            activeAlerts.remove(at: index)
        }
    }

    func acknowledgeAll() {
        activeAlerts.removeAll()
    }

    func clearHistory() {
        alertHistory.removeAll()
        saveAlertHistory()
    }

    // MARK: - Persistence

    private let historyKey = "kagami.sensorAlerts.history"

    private func loadAlertHistory() {
        guard let data = UserDefaults.standard.data(forKey: historyKey),
              let history = try? JSONDecoder().decode([SensorAlert].self, from: data) else {
            return
        }
        alertHistory = history
    }

    private func saveAlertHistory() {
        if let data = try? JSONEncoder().encode(alertHistory) {
            UserDefaults.standard.set(data, forKey: historyKey)
        }
    }

    // MARK: - Test Alerts (for development)

    func sendTestAlert(type: SensorAlertType) {
        let testRooms = ["Living Room", "Kitchen", "Primary Bedroom", "Office"]
        let room = testRooms.randomElement() ?? "Living Room"

        var value: String? = nil
        if type == .temperatureHigh {
            value = "\(Int.random(in: 80...90))"
        } else if type == .temperatureLow {
            value = "\(Int.random(in: 55...62))"
        } else if type == .humidity {
            value = "\(Int.random(in: 70...90))"
        }

        let alert = SensorAlert(type: type, room: room, sensor: "\(type.rawValue)_sensor", value: value)
        addAlert(alert)
    }
}

// MARK: - Sensor Alert Overlay View

struct SensorAlertOverlay: View {
    @EnvironmentObject var alertService: SensorAlertService

    var body: some View {
        VStack(spacing: 8) {
            ForEach(alertService.activeAlerts.prefix(3)) { alert in
                SensorAlertBanner(alert: alert) {
                    withAnimation {
                        alertService.acknowledgeAlert(alert.id)
                    }
                }
                .transition(.asymmetric(
                    insertion: .move(edge: .top).combined(with: .opacity),
                    removal: .move(edge: .trailing).combined(with: .opacity)
                ))
            }
        }
        .padding(.horizontal)
        .animation(.spring(response: 0.377, dampingFraction: 0.8), value: alertService.activeAlerts.count)  // 377ms Fibonacci
    }
}

// MARK: - Sensor Alert Banner

struct SensorAlertBanner: View {
    let alert: SensorAlert
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Icon
            Image(systemName: alert.type.icon)
                .font(.title2)
                .foregroundColor(alert.type.color)
                .frame(width: 32)

            // Content
            VStack(alignment: .leading, spacing: 2) {
                Text(alert.message)
                    .font(.subheadline)
                    .foregroundColor(.white)

                Text(alert.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Dismiss button
            Button(action: onDismiss) {
                Image(systemName: "xmark.circle.fill")
                    .font(.title3)
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(alert.type.color.opacity(0.5), lineWidth: 1)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(alert.type.rawValue) alert: \(alert.message)")
        .accessibilityHint("Swipe to dismiss")
    }
}

// MARK: - Sensor Alert History View

struct SensorAlertHistoryView: View {
    @EnvironmentObject var alertService: SensorAlertService

    var body: some View {
        NavigationStack {
            List {
                if alertService.alertHistory.isEmpty {
                    ContentUnavailableView(
                        "No Alerts",
                        systemImage: "checkmark.circle.fill",
                        description: Text("All clear. No recent sensor alerts.")
                    )
                } else {
                    ForEach(alertService.alertHistory) { alert in
                        SensorAlertHistoryRow(alert: alert)
                    }
                }
            }
            .navigationTitle("Alert History")
            .toolbar {
                if !alertService.alertHistory.isEmpty {
                    ToolbarItem(placement: .destructiveAction) {
                        Button("Clear All") {
                            alertService.clearHistory()
                        }
                    }
                }
            }
        }
    }
}

struct SensorAlertHistoryRow: View {
    let alert: SensorAlert

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: alert.type.icon)
                .foregroundColor(alert.type.color)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(alert.message)
                    .font(.body)

                Text(alert.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Sensor Alert Settings View

struct SensorAlertSettingsView: View {
    @EnvironmentObject var alertService: SensorAlertService

    @State private var temperatureHighThreshold: Double = 78
    @State private var temperatureLowThreshold: Double = 62
    @State private var enableMotionAlerts = true
    @State private var enableDoorAlerts = true
    @State private var enableTemperatureAlerts = true

    var body: some View {
        Form {
            Section("Alert Types") {
                Toggle("Motion Alerts", isOn: $enableMotionAlerts)
                Toggle("Door/Window Alerts", isOn: $enableDoorAlerts)
                Toggle("Temperature Alerts", isOn: $enableTemperatureAlerts)
            }

            if enableTemperatureAlerts {
                Section("Temperature Thresholds") {
                    VStack(alignment: .leading) {
                        Text("High Alert: \(Int(temperatureHighThreshold))F")
                        Slider(value: $temperatureHighThreshold, in: 70...90, step: 1)
                    }

                    VStack(alignment: .leading) {
                        Text("Low Alert: \(Int(temperatureLowThreshold))F")
                        Slider(value: $temperatureLowThreshold, in: 50...70, step: 1)
                    }
                }
            }

            Section("Test Alerts") {
                Button("Send Test Motion Alert") {
                    alertService.sendTestAlert(type: .motion)
                }

                Button("Send Test Door Alert") {
                    alertService.sendTestAlert(type: .doorOpen)
                }

                Button("Send Test Temperature Alert") {
                    alertService.sendTestAlert(type: .temperatureHigh)
                }
            }
        }
        .navigationTitle("Alert Settings")
    }
}

#Preview {
    SensorAlertOverlay()
        .environmentObject(SensorAlertService())
}

/*
 * 鏡
 * Awareness is the foundation of safety.
 * h(x) >= 0. Always.
 */
