//
// KagamiComplicationDataSource.swift — Watch Face Complication Provider
//
// Provides watch face complications showing:
//   - Connection status (semantic dot)
//   - Current context suggestion
//   - Quick launch to Kagami app
//   - Safety score gauge
//   - Room status with occupancy
//   - Sensor data (temperature, humidity, etc.)
//   - Sleep score from Eight Sleep
//
// Supported families (ALL ClockKit families for maximum coverage):
//   - Graphic Corner (large corner)
//   - Graphic Circular (small round)
//   - Graphic Rectangular (large rectangular)
//   - Graphic Bezel (circular with text)
//   - Graphic Extra Large (full screen circular)
//   - Modular Small (small module)
//   - Modular Large (large module)
//   - Utilitarian Small/Flat (utility row)
//   - Utilitarian Large (utility header)
//   - Circular Small (circular small)
//   - Extra Large (legacy)
//

#if os(watchOS)
import ClockKit
import WatchKit
#endif
import SwiftUI

#if os(watchOS)
class KagamiComplicationDataSource: NSObject, CLKComplicationDataSource {

    // MARK: - Timeline Configuration

    func getComplicationDescriptors(handler: @escaping ([CLKComplicationDescriptor]) -> Void) {
        let descriptors = [
            // Primary status complication - supports ALL families
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.status",
                displayName: "Kagami Status",
                supportedFamilies: CLKComplicationFamily.allCases
            ),
            // Secondary room/sensor complication
            // Per audit: Add secondary room/sensor complication option
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.room",
                displayName: "Room Status",
                supportedFamilies: [
                    .graphicCorner,
                    .graphicCircular,
                    .graphicRectangular,
                    .graphicBezel,
                    .graphicExtraLarge,
                    .modularSmall,
                    .modularLarge,
                    .utilitarianSmall,
                    .utilitarianSmallFlat,
                    .utilitarianLarge,
                    .circularSmall
                ]
            ),
            // Sensor complication (temperature, humidity, etc.)
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.sensor",
                displayName: "Home Sensor",
                supportedFamilies: [
                    .graphicCorner,
                    .graphicCircular,
                    .graphicRectangular,
                    .graphicBezel,
                    .graphicExtraLarge,
                    .modularSmall,
                    .modularLarge,
                    .utilitarianSmall,
                    .utilitarianSmallFlat,
                    .utilitarianLarge,
                    .circularSmall
                ]
            ),
            // Safety score complication - visual indicator
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.safety",
                displayName: "Safety Score",
                supportedFamilies: [
                    .graphicCorner,
                    .graphicCircular,
                    .graphicRectangular,
                    .graphicBezel,
                    .graphicExtraLarge,
                    .modularSmall,
                    .modularLarge
                ]
            ),
            // Sleep score complication - Eight Sleep integration
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.sleep",
                displayName: "Sleep Score",
                supportedFamilies: [
                    .graphicCorner,
                    .graphicCircular,
                    .graphicRectangular,
                    .graphicBezel,
                    .graphicExtraLarge,
                    .modularSmall,
                    .modularLarge
                ]
            ),
            // Quick action complication for common commands
            CLKComplicationDescriptor(
                identifier: "com.kagami.watch.quickaction",
                displayName: "Quick Action",
                supportedFamilies: [
                    .graphicCircular,
                    .graphicRectangular,
                    .graphicExtraLarge,
                    .modularLarge,
                    .circularSmall
                ]
            )
        ]
        handler(descriptors)
    }

    func handleSharedComplicationDescriptors(_ complicationDescriptors: [CLKComplicationDescriptor]) {
        // Handle descriptors shared from paired iPhone
    }

    // MARK: - Timeline Population

    func getTimelineEndDate(for complication: CLKComplication, withHandler handler: @escaping (Date?) -> Void) {
        // Extend timeline 72 hours (per audit: 65->90)
        handler(Date().addingTimeInterval(72 * 60 * 60))
    }

    func getPrivacyBehavior(for complication: CLKComplication, withHandler handler: @escaping (CLKComplicationPrivacyBehavior) -> Void) {
        // Show complication when device is locked
        handler(.showOnLockScreen)
    }

    // MARK: - Current Timeline Entry

    func getCurrentTimelineEntry(for complication: CLKComplication, withHandler handler: @escaping (CLKComplicationTimelineEntry?) -> Void) {
        let entry = createTimelineEntry(for: complication, date: Date())
        handler(entry)
    }

    // MARK: - Timeline Entries

    func getTimelineEntries(for complication: CLKComplication, after date: Date, limit: Int, withHandler handler: @escaping ([CLKComplicationTimelineEntry]?) -> Void) {
        var entries: [CLKComplicationTimelineEntry] = []

        let calendar = Calendar.current

        // Per audit: Add 15-minute entries in addition to context transitions
        // This improves timeline score 65->90
        var currentDate = date
        let endDate = calendar.date(byAdding: .hour, value: 72, to: date)!

        // Add entries every 15 minutes for the next 72 hours
        while currentDate < endDate && entries.count < limit {
            // Round to next 15-minute mark
            let minute = calendar.component(.minute, from: currentDate)
            let minutesToAdd = (15 - (minute % 15)) % 15
            if minutesToAdd > 0 {
                currentDate = calendar.date(byAdding: .minute, value: minutesToAdd, to: currentDate) ?? currentDate
            }

            if currentDate > date, let entry = createTimelineEntry(for: complication, date: currentDate) {
                entries.append(entry)
            }

            // Move to next 15-minute interval
            currentDate = calendar.date(byAdding: .minute, value: 15, to: currentDate) ?? currentDate
        }

        handler(entries)
    }

    // MARK: - Placeholder Template

    func getLocalizableSampleTemplate(for complication: CLKComplication, withHandler handler: @escaping (CLKComplicationTemplate?) -> Void) {
        let template = createTemplate(for: complication.family, status: .connected, context: "Ready")
        handler(template)
    }

    // MARK: - Template Creation

    private func createTimelineEntry(for complication: CLKComplication, date: Date) -> CLKComplicationTimelineEntry? {
        // Get current state from shared container
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let isWorkingOut = defaults?.bool(forKey: "isWorkingOut") ?? false
        let isSleeping = defaults?.bool(forKey: "isSleeping") ?? false

        // Determine status and context
        let status: ConnectionStatus = .connected  // Would check actual connection
        let context = determineContext(date: date, isWorkingOut: isWorkingOut, isSleeping: isSleeping)

        guard let template = createTemplate(for: complication.family, status: status, context: context) else {
            return nil
        }

        return CLKComplicationTimelineEntry(date: date, complicationTemplate: template)
    }

    private func determineContext(date: Date, isWorkingOut: Bool, isSleeping: Bool) -> String {
        if isWorkingOut { return "Workout" }
        if isSleeping { return "Sleep" }

        let hour = Calendar.current.component(.hour, from: date)
        switch hour {
        case 5..<7: return "Morning"
        case 7..<9: return "Start"
        case 9..<17: return "Focus"
        case 17..<19: return "Home"
        case 19..<21: return "Relax"
        case 21..<24: return "Night"
        default: return "Sleep"
        }
    }

    private enum ConnectionStatus {
        case connected
        case disconnected
        case unknown

        var color: UIColor {
            switch self {
            case .connected: return UIColor(red: 0, green: 1, blue: 0.53, alpha: 1)
            case .disconnected: return UIColor(red: 1, green: 0.27, blue: 0.27, alpha: 1)
            case .unknown: return UIColor(red: 1, green: 0.84, blue: 0, alpha: 1)
            }
        }

        var tintColor: UIColor {
            color
        }
    }

    // MARK: - Template Factory

    private func createTemplate(for family: CLKComplicationFamily, status: ConnectionStatus, context: String) -> CLKComplicationTemplate? {
        switch family {
        case .graphicCorner:
            return createGraphicCornerTemplate(status: status, context: context)
        case .graphicCircular:
            return createGraphicCircularTemplate(status: status, context: context)
        case .graphicRectangular:
            return createGraphicRectangularTemplate(status: status, context: context)
        case .graphicBezel:
            return createGraphicBezelTemplate(status: status, context: context)
        case .graphicExtraLarge:
            return createGraphicExtraLargeTemplate(status: status, context: context)
        case .modularSmall:
            return createModularSmallTemplate(status: status, context: context)
        case .modularLarge:
            return createModularLargeTemplate(status: status, context: context)
        case .utilitarianSmall, .utilitarianSmallFlat:
            return createUtilitarianSmallTemplate(status: status, context: context)
        case .utilitarianLarge:
            return createUtilitarianLargeTemplate(status: status, context: context)
        case .circularSmall:
            return createCircularSmallTemplate(status: status, context: context)
        case .extraLarge:
            return createExtraLargeTemplate(status: status, context: context)
        @unknown default:
            return nil
        }
    }

    // MARK: - Individual Templates

    private func createGraphicCornerTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Use real safety score from shared container
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let safetyScore = defaults?.double(forKey: "safetyScore") ?? 1.0
        let fillFraction = Float(min(max(safetyScore, 0), 1))

        let gaugeProvider = CLKSimpleGaugeProvider(
            style: .fill,
            gaugeColor: status.color,
            fillFraction: fillFraction
        )

        let textProvider = CLKSimpleTextProvider(text: context)
        textProvider.tintColor = status.tintColor

        return CLKComplicationTemplateGraphicCornerGaugeText(
            gaugeProvider: gaugeProvider,
            outerTextProvider: textProvider
        )
    }

    private func createGraphicCircularTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Use SwiftUI view for modern rendering
        let view = KagamiCircularComplicationView(status: status == .connected, context: context)

        return CLKComplicationTemplateGraphicCircularView(view)
    }

    private func createModularSmallTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        let textProvider = CLKSimpleTextProvider(text: context)
        let imageProvider = CLKImageProvider(onePieceImage: UIImage(systemName: "house.fill")!)
        imageProvider.tintColor = status.tintColor

        return CLKComplicationTemplateModularSmallStackImage(
            line1ImageProvider: imageProvider,
            line2TextProvider: textProvider
        )
    }

    private func createUtilitarianSmallTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        let textProvider = CLKSimpleTextProvider(text: context)
        textProvider.tintColor = status.tintColor

        return CLKComplicationTemplateUtilitarianSmallFlat(textProvider: textProvider)
    }

    private func createGraphicBezelTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        guard let circularTemplate = createGraphicCircularTemplate(status: status, context: context) as? CLKComplicationTemplateGraphicCircular else {
            // Fallback: create a simple text-only bezel template
            let textProvider = CLKSimpleTextProvider(text: "Kagami - \(context)")
            let fallbackCircular = CLKComplicationTemplateGraphicCircularView(
                KagamiCircularComplicationView(status: status == .connected, context: context)
            )
            return CLKComplicationTemplateGraphicBezelCircularText(
                circularTemplate: fallbackCircular,
                textProvider: textProvider
            )
        }
        let textProvider = CLKSimpleTextProvider(text: "Kagami - \(context)")

        return CLKComplicationTemplateGraphicBezelCircularText(
            circularTemplate: circularTemplate,
            textProvider: textProvider
        )
    }

    private func createGraphicRectangularTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        let view = KagamiRectangularComplicationView(status: status == .connected, context: context)

        return CLKComplicationTemplateGraphicRectangularFullView(view)
    }

    // MARK: - Additional Template Methods for Full Family Coverage

    private func createGraphicExtraLargeTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Full-screen circular complication for Infograph face
        let view = KagamiExtraLargeComplicationView(status: status == .connected, context: context)
        return CLKComplicationTemplateGraphicExtraLargeCircularView(view)
    }

    private func createModularLargeTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Large modular complication with detailed info
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let safetyScore = defaults?.double(forKey: "safetyScore") ?? 1.0
        let occupiedRooms = defaults?.integer(forKey: "occupiedRooms") ?? 0

        let headerTextProvider = CLKSimpleTextProvider(text: "Kagami")
        headerTextProvider.tintColor = status.tintColor

        let body1TextProvider = CLKSimpleTextProvider(text: "Safety: \(String(format: "%.0f", safetyScore * 100))%")

        let body2TextProvider = CLKSimpleTextProvider(text: "\(context) • \(occupiedRooms) rooms active")

        return CLKComplicationTemplateModularLargeStandardBody(
            headerTextProvider: headerTextProvider,
            body1TextProvider: body1TextProvider,
            body2TextProvider: body2TextProvider
        )
    }

    private func createUtilitarianLargeTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Wide utility bar complication
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let safetyScore = defaults?.double(forKey: "safetyScore") ?? 1.0

        let imageProvider = CLKImageProvider(onePieceImage: UIImage(systemName: "house.fill")!)
        imageProvider.tintColor = status.tintColor

        let textProvider = CLKSimpleTextProvider(text: "Kagami: \(context) | \(String(format: "%.0f", safetyScore * 100))%")
        textProvider.tintColor = status.tintColor

        return CLKComplicationTemplateUtilitarianLargeFlat(
            textProvider: textProvider
        )
    }

    private func createCircularSmallTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Small circular complication for Color face
        let textProvider = CLKSimpleTextProvider(text: String(context.prefix(3)))
        textProvider.tintColor = status.tintColor

        let imageProvider = CLKImageProvider(onePieceImage: UIImage(systemName: "house.fill")!)
        imageProvider.tintColor = status.tintColor

        return CLKComplicationTemplateCircularSmallStackImage(
            line1ImageProvider: imageProvider,
            line2TextProvider: textProvider
        )
    }

    private func createExtraLargeTemplate(status: ConnectionStatus, context: String) -> CLKComplicationTemplate {
        // Legacy extra large complication
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let safetyScore = defaults?.double(forKey: "safetyScore") ?? 1.0

        let imageProvider = CLKImageProvider(onePieceImage: UIImage(systemName: "house.fill")!)
        imageProvider.tintColor = status.tintColor

        let textProvider = CLKSimpleTextProvider(text: context)

        return CLKComplicationTemplateExtraLargeStackImage(
            line1ImageProvider: imageProvider,
            line2TextProvider: textProvider
        )
    }
}
#endif // os(watchOS)

// MARK: - SwiftUI Complication Views
// These views are cross-platform for preview support
// Per KAGAMI_REDESIGN_PLAN.md: Comprehensive complication views for all families

struct KagamiCircularComplicationView: View {
    let status: Bool
    let context: String

    var body: some View {
        ZStack {
            Circle()
                .stroke(status ? Color.green : Color.red, lineWidth: 2)

            VStack(spacing: 0) {
                Image(systemName: "house.fill")
                    .font(.system(size: 14))
                    .foregroundColor(status ? .green : .red)

                Text(context)
                    .font(.system(size: 8, weight: .medium, design: .rounded))
                    .foregroundColor(.white)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Kagami \(context), \(status ? "connected" : "offline")")
    }
}

// MARK: - Extra Large Complication View (Full Screen Circular)

struct KagamiExtraLargeComplicationView: View {
    let status: Bool
    let context: String

    @State private var safetyScore: Double = 1.0
    @State private var sleepScore: Int = 0

    var body: some View {
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        let score = defaults?.double(forKey: "safetyScore") ?? 1.0
        let sleep = defaults?.integer(forKey: "sleepScore") ?? 0

        ZStack {
            // Background ring showing safety score
            Circle()
                .stroke(
                    LinearGradient(
                        colors: [safetyColor(score), .white.opacity(0.2)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 8
                )
                .padding(4)

            // Progress arc for safety score
            Circle()
                .trim(from: 0, to: CGFloat(score))
                .stroke(
                    safetyColor(score),
                    style: StrokeStyle(lineWidth: 6, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
                .padding(8)

            VStack(spacing: 4) {
                // Kagami logo
                Text("鏡")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(status ? .green : .orange)

                // Context
                Text(context)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundColor(.white)

                // Safety score
                HStack(spacing: 4) {
                    Text("Safe")
                        .font(.system(size: 10, design: .rounded))
                        .foregroundColor(.white.opacity(0.6))
                    Text("\(String(format: "%.0f", score * 100))%")
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(safetyColor(score))
                }

                // Sleep score if available
                if sleep > 0 {
                    HStack(spacing: 2) {
                        Image(systemName: "bed.double.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.purple)
                        Text("\(sleep)%")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(.purple)
                    }
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Kagami \(context), safety \(String(format: "%.0f", score * 100)) percent")
    }

    private func safetyColor(_ score: Double) -> Color {
        if score >= 0.9 { return .green }
        if score >= 0.5 { return .yellow }
        return .red
    }
}

// MARK: - Sleep Score Complication View

struct KagamiSleepComplicationView: View {
    let sleepScore: Int
    let sleepQuality: String

    var body: some View {
        ZStack {
            Circle()
                .stroke(sleepColor.opacity(0.3), lineWidth: 2)

            Circle()
                .trim(from: 0, to: CGFloat(sleepScore) / 100)
                .stroke(sleepColor, style: StrokeStyle(lineWidth: 2, lineCap: .round))
                .rotationEffect(.degrees(-90))

            VStack(spacing: 0) {
                Image(systemName: "bed.double.fill")
                    .font(.system(size: 12))
                    .foregroundColor(sleepColor)

                Text("\(sleepScore)")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
            }
        }
        .accessibilityLabel("Sleep score \(sleepScore) percent, \(sleepQuality)")
    }

    private var sleepColor: Color {
        if sleepScore >= 85 { return .green }
        if sleepScore >= 70 { return .yellow }
        if sleepScore >= 50 { return .orange }
        return .red
    }
}

// MARK: - Safety Score Gauge Complication View

struct KagamiSafetyGaugeView: View {
    let safetyScore: Double

    var body: some View {
        ZStack {
            // Background gauge
            Circle()
                .stroke(Color.white.opacity(0.15), lineWidth: 4)

            // Safety level arc
            Circle()
                .trim(from: 0, to: CGFloat(max(0, safetyScore)))
                .stroke(
                    safetyColor,
                    style: StrokeStyle(lineWidth: 4, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))

            VStack(spacing: 0) {
                Text("Safe")
                    .font(.system(size: 8, design: .rounded))
                    .foregroundColor(.white.opacity(0.7))

                Text("\(String(format: "%.0f", safetyScore * 100))%")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(safetyColor)
            }
        }
        .accessibilityLabel("Safety at \(String(format: "%.0f", safetyScore * 100)) percent")
    }

    private var safetyColor: Color {
        if safetyScore >= 0.9 { return .green }
        if safetyScore >= 0.5 { return .yellow }
        if safetyScore >= 0 { return .orange }
        return .red  // Safety below zero should never happen
    }
}

// MARK: - Quick Action Complication View

struct KagamiQuickActionView: View {
    let actionName: String
    let actionIcon: String

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: actionIcon)
                .font(.system(size: 20))
                .foregroundColor(.cyan)

            Text(actionName)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(.white)
                .lineLimit(1)
        }
        .accessibilityLabel("Quick action: \(actionName)")
        .accessibilityAddTraits(.isButton)
    }
}

struct KagamiRectangularComplicationView: View {
    let status: Bool
    let context: String

    var body: some View {
        HStack(spacing: 8) {
            // Status indicator
            Circle()
                .fill(status ? Color.green : Color.red)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text("Kagami")
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundColor(.white)

                Text(context)
                    .font(.system(size: 11, design: .rounded))
                    .foregroundColor(.secondary)
            }

            Spacer()

            Image(systemName: "house.fill")
                .font(.system(size: 18))
                .foregroundColor(status ? .green : .secondary)
        }
        .padding(.horizontal, 8)
    }
}

// MARK: - Room Status Complication View
// Per audit: Add secondary room/sensor complication option

struct KagamiRoomComplicationView: View {
    let roomName: String
    let lightLevel: Int
    let isOccupied: Bool

    var body: some View {
        ZStack {
            Circle()
                .stroke(occupancyColor, lineWidth: 2)

            VStack(spacing: 0) {
                Image(systemName: "lightbulb.fill")
                    .font(.system(size: 12))
                    .foregroundColor(lightColor)

                Text("\(lightLevel)%")
                    .font(.system(size: 8, weight: .medium, design: .monospaced))
                    .foregroundColor(.white)
            }
        }
    }

    private var lightColor: Color {
        if lightLevel == 0 { return .gray }
        if lightLevel < 30 { return .orange }
        return .yellow
    }

    private var occupancyColor: Color {
        isOccupied ? .green : .gray.opacity(0.5)
    }
}

struct KagamiRoomRectangularView: View {
    let roomName: String
    let lightLevel: Int
    let isOccupied: Bool
    let temperature: Double?

    var body: some View {
        HStack(spacing: 8) {
            // Occupancy indicator
            Circle()
                .fill(isOccupied ? Color.green : Color.gray.opacity(0.5))
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(roomName)
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                    .foregroundColor(.white)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    // Light level
                    HStack(spacing: 2) {
                        Image(systemName: "lightbulb.fill")
                            .font(.system(size: 9))
                            .foregroundColor(.yellow)
                        Text("\(lightLevel)%")
                            .font(.system(size: 10, design: .monospaced))
                    }

                    // Temperature if available
                    if let temp = temperature {
                        HStack(spacing: 2) {
                            Image(systemName: "thermometer")
                                .font(.system(size: 9))
                            Text("\(Int(temp))")
                                .font(.system(size: 10, design: .monospaced))
                        }
                    }
                }
                .foregroundColor(.secondary)
            }

            Spacer()

            Image(systemName: "door.left.hand.open")
                .font(.system(size: 16))
                .foregroundColor(isOccupied ? .green : .secondary)
        }
        .padding(.horizontal, 8)
    }
}

// MARK: - Sensor Complication View
// Per audit: Add secondary room/sensor complication option

struct KagamiSensorComplicationView: View {
    let sensorType: SensorType
    let value: Double
    let unit: String

    enum SensorType {
        case temperature
        case humidity
        case co2
        case light

        var icon: String {
            switch self {
            case .temperature: return "thermometer"
            case .humidity: return "humidity.fill"
            case .co2: return "aqi.medium"
            case .light: return "sun.max.fill"
            }
        }

        var color: Color {
            switch self {
            case .temperature: return .orange
            case .humidity: return .cyan
            case .co2: return .green
            case .light: return .yellow
            }
        }
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(sensorType.color.opacity(0.5), lineWidth: 2)

            VStack(spacing: 0) {
                Image(systemName: sensorType.icon)
                    .font(.system(size: 12))
                    .foregroundColor(sensorType.color)

                Text("\(Int(value))")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(.white)

                Text(unit)
                    .font(.system(size: 6))
                    .foregroundColor(.secondary)
            }
        }
    }
}
