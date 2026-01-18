//
// AppDelegate.swift — Kagami iOS App Delegate
//
// Handles CarPlay scene configuration.
// Colony: Nexus (e4) — Integration
// h(x) ≥ 0. Always.
//

import UIKit
#if canImport(CarPlay)
import CarPlay
#endif

class AppDelegate: NSObject, UIApplicationDelegate {

    func application(_ application: UIApplication, configurationForConnecting connectingSceneSession: UISceneSession, options: UIScene.ConnectionOptions) -> UISceneConfiguration {

        #if canImport(CarPlay)
        // CarPlay scene
        if connectingSceneSession.role == .carTemplateApplication {
            let configuration = UISceneConfiguration(name: "CarPlay Configuration", sessionRole: .carTemplateApplication)
            configuration.delegateClass = KagamiCarPlaySceneDelegate.self
            return configuration
        }
        #endif

        // Default scene (main app)
        let configuration = UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
        return configuration
    }

    func application(_ application: UIApplication, didDiscardSceneSessions sceneSessions: Set<UISceneSession>) {
        // Handle discarded scenes
    }
}

// MARK: - CarPlay Scene Delegate

#if canImport(CarPlay)

class KagamiCarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {

    private var interfaceController: CPInterfaceController?
    private let homeState = CarPlayHomeState()

    // MARK: - Scene Lifecycle

    func templateApplicationScene(_ templateApplicationScene: CPTemplateApplicationScene,
                                  didConnect interfaceController: CPInterfaceController) {
        self.interfaceController = interfaceController

        // Set up the root template
        let rootTemplate = createRootTemplate()
        interfaceController.setRootTemplate(rootTemplate, animated: true, completion: nil)
    }

    func templateApplicationScene(_ templateApplicationScene: CPTemplateApplicationScene,
                                  didDisconnect interfaceController: CPInterfaceController) {
        self.interfaceController = nil
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
            ("arriving_home", "Arriving Home", "🏡", "Lights on, temp adjusted"),
            ("leaving_home", "Leaving Home", "🔒", "Lock up, lights off"),
            ("movie_mode", "Movie Mode", "🎬", "Theater ready"),
            ("goodnight", "Goodnight", "🌙", "All off, locked up"),
        ]

        let items = scenes.map { scene -> CPListItem in
            let item = CPListItem(
                text: "\(scene.2) \(scene.1)",
                detailText: scene.3
            )
            item.accessoryType = .disclosureIndicator
            item.handler = { [weak self] _, completion in
                self?.executeScene(scene.0)
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
            ("garage", "Garage Door", "car.garage"),
            ("front_door", "Front Door", "door.garage.closed"),
            ("lights_on", "All Lights On", "lightbulb.fill"),
            ("lights_off", "All Lights Off", "lightbulb"),
        ]

        let items = controls.map { control -> CPListItem in
            let item = CPListItem(
                text: control.1,
                detailText: nil,
                image: UIImage(systemName: control.2)
            )
            item.handler = { [weak self] _, completion in
                self?.executeControl(control.0)
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
            ("precool", "Pre-Cool Home", "snowflake", 68),
            ("preheat", "Pre-Heat Home", "flame", 72),
        ]

        let items = climateActions.map { action -> CPListItem in
            let subtitle = "Target: \(action.3)°F"
            let item = CPListItem(
                text: action.1,
                detailText: subtitle,
                image: UIImage(systemName: action.2)
            )
            item.handler = { [weak self] _, completion in
                self?.executeClimate(action.0, temp: action.3)
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
            let success = await homeState.executeScene(sceneId)
            showResult(success: success, title: "Scene", message: sceneId.replacingOccurrences(of: "_", with: " ").capitalized)
        }
    }

    private func executeControl(_ controlId: String) {
        Task {
            let success = await homeState.executeControl(controlId)
            showResult(success: success, title: "Control", message: controlId.replacingOccurrences(of: "_", with: " ").capitalized)
        }
    }

    private func executeClimate(_ action: String, temp: Int) {
        Task {
            let success = await homeState.setClimate(temp)
            showResult(success: success, title: "Climate", message: "\(temp)°F")
        }
    }

    private func showResult(success: Bool, title: String, message: String) {
        let okAction = CPAlertAction(title: "OK", style: .default) { [weak self] _ in
            self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
        }

        let alertTitle = success ? "✅ \(title)" : "❌ \(title) Failed"
        let alert = CPAlertTemplate(
            titleVariants: [alertTitle, message],
            actions: [okAction]
        )

        interfaceController?.presentTemplate(alert, animated: true) { _, _ in
            // Auto-dismiss after 2 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                self?.interfaceController?.dismissTemplate(animated: true, completion: nil)
            }
        }
    }
}

// MARK: - CarPlay Home State

class CarPlayHomeState {
    // Security: Default to HTTPS production URL. Local dev via UserDefaults.
    private let apiURL: String = {
        if let saved = UserDefaults.standard.string(forKey: "kagamiServerURL") {
            return saved
        }
        return "https://api.awkronos.com"
    }()

    func executeScene(_ sceneId: String) async -> Bool {
        return await postRequest(endpoint: "/api/home/\(sceneId.replacingOccurrences(of: "_", with: "-"))")
    }

    func executeControl(_ controlId: String) async -> Bool {
        switch controlId {
        case "garage":
            return await postRequest(endpoint: "/api/home/garage/toggle")
        case "front_door":
            return await postRequest(endpoint: "/api/home/locks/unlock", body: ["door_name": "Front Door"])
        case "lights_on":
            return await postRequest(endpoint: "/api/home/lights/set", body: ["level": 100])
        case "lights_off":
            return await postRequest(endpoint: "/api/home/lights/set", body: ["level": 0])
        default:
            return false
        }
    }

    func setClimate(_ targetTemp: Int) async -> Bool {
        return await postRequest(endpoint: "/api/home/climate/set", body: ["target_temp": targetTemp])
    }

    private func postRequest(endpoint: String, body: [String: Any]? = nil) async -> Bool {
        guard let url = URL(string: "\(apiURL)\(endpoint)") else { return false }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("kagami-carplay", forHTTPHeaderField: "User-Agent")

        if let body = body {
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode ?? 0 >= 200 && (response as? HTTPURLResponse)?.statusCode ?? 0 < 300
        } catch {
            return false
        }
    }
}

#endif // canImport(CarPlay)

/*
 * 鏡
 * CarPlay brings Kagami to the road.
 * Arriving home has never been smarter.
 */
