//
// KagamiCarPlaySceneDelegate.swift — CarPlay Interface
//
// Colony: Nexus (e₄) — Integration
//
// CarPlay Features:
//   - Arriving home automation trigger
//   - Quick scene activation
//   - Climate pre-conditioning
//   - Garage door control
//   - Voice commands
//

#if canImport(CarPlay)
import CarPlay
import SwiftUI
import CoreLocation

// MARK: - CarPlay Scene Delegate

class KagamiCarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {

    private var interfaceController: CPInterfaceController?
    private let locationManager = CarPlayLocationManager.shared
    private let apiService = KagamiAPIService.shared

    // MARK: - Scene Lifecycle

    func templateApplicationScene(_ templateApplicationScene: CPTemplateApplicationScene,
                                  didConnect interfaceController: CPInterfaceController) {
        self.interfaceController = interfaceController

        // Set up the root template
        let rootTemplate = createRootTemplate()
        interfaceController.setRootTemplate(rootTemplate, animated: true, completion: nil)

        // Start monitoring location for arriving home
        locationManager.startMonitoringHomeProximity()
        locationManager.onArrivingHome = { [weak self] in
            self?.handleArrivingHome()
        }
    }

    func templateApplicationScene(_ templateApplicationScene: CPTemplateApplicationScene,
                                  didDisconnect interfaceController: CPInterfaceController) {
        self.interfaceController = nil
        locationManager.stopMonitoring()
    }

    // MARK: - Root Template

    private func createRootTemplate() -> CPTemplate {
        // Create tab bar with main sections
        let scenesTab = createScenesTemplate()
        let homeTab = createHomeControlTemplate()
        let climateTab = createClimateTemplate()

        scenesTab.tabImage = UIImage(systemName: "sparkles")
        homeTab.tabImage = UIImage(systemName: "house")
        climateTab.tabImage = UIImage(systemName: "thermometer")

        let tabBarTemplate = CPTabBarTemplate(templates: [scenesTab, homeTab, climateTab])
        return tabBarTemplate
    }

    // MARK: - Scenes Template

    private func createScenesTemplate() -> CPListTemplate {
        let scenes = [
            SceneItem(id: "arriving_home", title: "Arriving Home", icon: "🏡", subtitle: "Lights on, temp adjusted"),
            SceneItem(id: "leaving_home", title: "Leaving Home", icon: "🔒", subtitle: "Lock up, lights off"),
            SceneItem(id: "movie_mode", title: "Movie Mode", icon: "🎬", subtitle: "Theater ready"),
            SceneItem(id: "goodnight", title: "Goodnight", icon: "🌙", subtitle: "All off, locked up"),
        ]

        let items = scenes.map { scene -> CPListItem in
            let item = CPListItem(
                text: "\(scene.icon) \(scene.title)",
                detailText: scene.subtitle
            )
            // VoiceOver accessibility
            item.accessoryType = .disclosureIndicator
            item.handler = { [weak self] _, completion in
                self?.executeScene(scene.id)
                completion()
            }
            return item
        }

        let section = CPListSection(items: items, header: "Quick Scenes", sectionIndexTitle: nil)
        let template = CPListTemplate(title: "Scenes", sections: [section])
        template.tabTitle = "Scenes"
        return template
    }

    // MARK: - Home Control Template

    private func createHomeControlTemplate() -> CPListTemplate {
        let controls = [
            ControlItem(id: "garage", title: "Garage Door", icon: "car.garage", type: .button),
            ControlItem(id: "front_door", title: "Front Door", icon: "door.garage.closed", type: .button),
            ControlItem(id: "lights_on", title: "All Lights On", icon: "lightbulb.fill", type: .button),
            ControlItem(id: "lights_off", title: "All Lights Off", icon: "lightbulb", type: .button),
        ]

        let items = controls.map { control -> CPListItem in
            let item = CPListItem(
                text: control.title,
                detailText: nil,
                image: UIImage(systemName: control.icon)
            )
            item.handler = { [weak self] _, completion in
                self?.executeControl(control.id)
                completion()
            }
            return item
        }

        let section = CPListSection(items: items, header: "Controls", sectionIndexTitle: nil)
        let template = CPListTemplate(title: "Home", sections: [section])
        template.tabTitle = "Home"
        return template
    }

    // MARK: - Climate Template

    private func createClimateTemplate() -> CPListTemplate {
        let climateActions = [
            ClimateAction(id: "precool", title: "Pre-Cool Home", icon: "snowflake", targetTemp: 68),
            ClimateAction(id: "preheat", title: "Pre-Heat Home", icon: "flame", targetTemp: 72),
            ClimateAction(id: "eco_mode", title: "Eco Mode", icon: "leaf", targetTemp: nil),
        ]

        let items = climateActions.map { action -> CPListItem in
            let subtitle = action.targetTemp != nil ? "Target: \(action.targetTemp!)°F" : "Energy saving"
            let item = CPListItem(
                text: action.title,
                detailText: subtitle,
                image: UIImage(systemName: action.icon)
            )
            item.handler = { [weak self] _, completion in
                self?.executeClimate(action)
                completion()
            }
            return item
        }

        let section = CPListSection(items: items, header: "Climate Control", sectionIndexTitle: nil)
        let template = CPListTemplate(title: "Climate", sections: [section])
        template.tabTitle = "Climate"
        return template
    }

    // MARK: - Actions

    private func executeScene(_ sceneId: String) {
        Task {
            let success = await apiService.executeScene(sceneId)
            if success {
                showNotification(title: "Scene Activated", message: sceneId.replacingOccurrences(of: "_", with: " ").capitalized)
            } else {
                showError(title: "Scene Failed", message: "Could not activate \(sceneId.replacingOccurrences(of: "_", with: " "))")
            }
        }
    }

    private func executeControl(_ controlId: String) {
        Task {
            var success = false
            var controlName = controlId

            switch controlId {
            case "garage":
                success = await apiService.toggleGarage()
                controlName = "Garage"
            case "front_door":
                success = await apiService.unlockDoor(named: "Front Door")
                controlName = "Front Door"
            case "lights_on":
                success = await apiService.setLights(100)
                controlName = "Lights"
            case "lights_off":
                success = await apiService.setLights(0)
                controlName = "Lights"
            default:
                return
            }

            if success {
                showNotification(title: "Success", message: "\(controlName) command sent")
            } else {
                showError(title: "Failed", message: "Could not control \(controlName)")
            }
        }
    }

    private func executeClimate(_ action: ClimateAction) {
        Task {
            var success = false

            if let temp = action.targetTemp {
                // Pre-condition to target temp
                success = await apiService.setClimate(temp)
            } else {
                success = await apiService.executeScene("eco_mode")
            }

            if success {
                showNotification(title: "Climate", message: "\(action.title) activated")
            } else {
                showError(title: "Climate Failed", message: "Could not set \(action.title)")
            }
        }
    }

    // MARK: - Arriving Home

    private func handleArrivingHome() {
        // Show arriving home alert with VoiceOver accessibility
        let activateAction = CPAlertAction(title: "Activate Arriving Home", style: .default) { [weak self] _ in
            self?.executeScene("arriving_home")
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
        }

        let cancelAction = CPAlertAction(title: "Not Now", style: .cancel) { [weak self] _ in
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
        }

        let alert = CPAlertTemplate(
            titleVariants: [
                "Welcome Home",
                "Arriving Home - Ready to activate your home scene"
            ],
            actions: [activateAction, cancelAction]
        )

        interfaceController?.presentTemplate(alert, animated: true, completion: nil)
    }

    private func showNotification(title: String, message: String) {
        // CarPlay alert with VoiceOver-friendly title variants
        // First variant is primary, subsequent variants provide more context
        let okAction = CPAlertAction(title: "OK", style: .default) { [weak self] _ in
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
        }

        let alert = CPAlertTemplate(
            titleVariants: [
                title,
                "\(title): \(message)",
                "Kagami notification: \(title). \(message)"
            ],
            actions: [okAction]
        )

        interfaceController?.presentTemplate(alert, animated: true) { _, _ in
            // Auto-dismiss after 2 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
            }
        }
    }

    private func showError(title: String, message: String) {
        // Error alert with VoiceOver accessibility
        // Provides clear context for screen reader users
        let dismissAction = CPAlertAction(title: "Dismiss", style: .cancel) { [weak self] _ in
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
        }

        let retryAction = CPAlertAction(title: "Retry", style: .default) { [weak self] _ in
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
            // Note: Retry logic would need context about what failed
        }

        let alert = CPAlertTemplate(
            titleVariants: [
                title,
                "Error: \(title). \(message)",
                "Kagami error: \(title). \(message). Select Retry to try again or Dismiss to close."
            ],
            actions: [dismissAction, retryAction]
        )

        interfaceController?.presentTemplate(alert, animated: true, completion: nil)
    }
}

// MARK: - Data Models

struct SceneItem {
    let id: String
    let title: String
    let icon: String
    let subtitle: String
}

struct ControlItem {
    let id: String
    let title: String
    let icon: String
    let type: ControlType

    enum ControlType {
        case button
        case toggle
    }
}

struct ClimateAction {
    let id: String
    let title: String
    let icon: String
    let targetTemp: Int?
}

// MARK: - Location Manager for Home Proximity

class CarPlayLocationManager: NSObject, CLLocationManagerDelegate {

    static let shared = CarPlayLocationManager()

    private let locationManager = CLLocationManager()
    private var homeRegion: CLCircularRegion?

    var onArrivingHome: (() -> Void)?

    // MARK: - Home Location Configuration

    /// UserDefaults keys for home location
    private enum UserDefaultsKeys {
        static let homeLatitude = "kagami_home_latitude"
        static let homeLongitude = "kagami_home_longitude"
        static let geofenceRadius = "kagami_geofence_radius"
    }

    /// Home coordinates - loaded from UserDefaults or falls back to nil (disabled)
    private var homeCoordinate: CLLocationCoordinate2D? {
        let defaults = UserDefaults.standard

        // Check if coordinates have been configured
        guard defaults.object(forKey: UserDefaultsKeys.homeLatitude) != nil,
              defaults.object(forKey: UserDefaultsKeys.homeLongitude) != nil else {
            return nil
        }

        let latitude = defaults.double(forKey: UserDefaultsKeys.homeLatitude)
        let longitude = defaults.double(forKey: UserDefaultsKeys.homeLongitude)

        // Validate coordinates are within valid ranges
        guard latitude >= -90 && latitude <= 90,
              longitude >= -180 && longitude <= 180 else {
            return nil
        }

        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    /// Geofence radius in meters - defaults to 200m if not configured
    private var geofenceRadius: CLLocationDistance {
        let radius = UserDefaults.standard.double(forKey: UserDefaultsKeys.geofenceRadius)
        return radius > 0 ? radius : 200.0
    }

    /// Configure home location for geofencing
    /// - Parameters:
    ///   - latitude: Home latitude (-90 to 90)
    ///   - longitude: Home longitude (-180 to 180)
    ///   - radius: Geofence radius in meters (default 200)
    static func configureHomeLocation(latitude: Double, longitude: Double, radius: Double = 200) {
        let defaults = UserDefaults.standard
        defaults.set(latitude, forKey: UserDefaultsKeys.homeLatitude)
        defaults.set(longitude, forKey: UserDefaultsKeys.homeLongitude)
        defaults.set(radius, forKey: UserDefaultsKeys.geofenceRadius)

        // Restart monitoring with new location
        shared.stopMonitoring()
        shared.startMonitoringHomeProximity()
    }

    /// Check if home location has been configured
    static var isHomeLocationConfigured: Bool {
        shared.homeCoordinate != nil
    }

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func startMonitoringHomeProximity() {
        guard CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self) else {
            return
        }

        // Only monitor if home location is configured
        guard let coordinate = homeCoordinate else {
            // Home location not configured - skip geofencing
            return
        }

        locationManager.requestAlwaysAuthorization()

        homeRegion = CLCircularRegion(
            center: coordinate,
            radius: geofenceRadius,
            identifier: "kagami_home"
        )
        homeRegion?.notifyOnEntry = true
        homeRegion?.notifyOnExit = false

        if let region = homeRegion {
            locationManager.startMonitoring(for: region)
        }
    }

    func stopMonitoring() {
        if let region = homeRegion {
            locationManager.stopMonitoring(for: region)
        }
    }

    // MARK: - CLLocationManagerDelegate

    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        if region.identifier == "kagami_home" {
            onArrivingHome?()
        }
    }
}

// MARK: - API Extensions for CarPlay

extension KagamiAPIService {

    /// Toggle garage door (CarPlay convenience method)
    @discardableResult
    func toggleGarage() async -> Bool {
        await postRequest(endpoint: "/home/garage/toggle")
    }

    /// Unlock a door by name (CarPlay convenience method)
    @discardableResult
    func unlockDoor(named name: String) async -> Bool {
        let body: [String: Any] = ["door_name": name]
        return await postRequest(endpoint: "/home/locks/unlock", body: body)
    }

    /// Set climate target temperature (CarPlay convenience method)
    @discardableResult
    func setClimate(_ targetTemp: Int) async -> Bool {
        let body: [String: Any] = ["target_temp": targetTemp]
        return await postRequest(endpoint: "/home/climate/set", body: body)
    }

    // Note: postRequest is now defined in the main KagamiAPIService class
    // and is available as a public method for all extensions to use
}

/*
 * 鏡
 * CarPlay brings Kagami to the road.
 * Arriving home has never been smarter.
 */

#endif // canImport(CarPlay)
