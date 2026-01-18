//
// LoginView.swift -- Authentication UI for Kagami iOS
//
// Colony: Nexus (e4) -- Integration
//
// Features:
//   - Server URL configuration with mDNS discovery
//   - Username/password authentication via /api/user/token
//   - Face ID / Touch ID biometric authentication
//   - Create account option for registration
//   - Secure token storage in Keychain
//   - Accessibility-first design (WCAG 2.1 AA)
//

import SwiftUI
import KagamiCore
import Network
import LocalAuthentication
import KagamiDesign

// MARK: - Login View

struct LoginView: View {
    @EnvironmentObject var appModel: AppModel
    @Binding var isAuthenticated: Bool

    // Form state
    @State private var serverURL: String = ""
    @State private var username: String = ""
    @State private var password: String = ""

    // UI state
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""
    @State private var showCreateAccount = false
    @State private var isDiscoveringServers = false
    @State private var discoveredServers: [DiscoveredServer] = []
    @State private var showServerPicker = false

    // Biometric state
    @State private var biometricType: BiometricType = .none
    @State private var canUseBiometrics = false

    // mDNS browser
    @State private var browser: NWBrowser?

    var body: some View {
        ZStack {
            // Background
            Color.void
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 32) {
                    // Header
                    headerSection

                    // Server configuration
                    serverSection

                    // Credentials
                    credentialsSection

                    // Actions
                    actionsSection

                    // Footer
                    footerSection
                }
                .padding(24)
            }
        }
        .alert("Login Failed", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage)
        }
        .sheet(isPresented: $showCreateAccount) {
            CreateAccountView(
                serverURL: serverURL,
                onAccountCreated: { token in
                    handleSuccessfulAuth(token: token)
                }
            )
            .environmentObject(appModel)
        }
        .sheet(isPresented: $showServerPicker) {
            ServerPickerView(
                servers: discoveredServers,
                onSelect: { server in
                    serverURL = server.url
                    showServerPicker = false
                }
            )
        }
        .onAppear {
            loadSavedServerURL()
            checkBiometricAvailability()
            // Auto-attempt biometric if token exists
            if KagamiKeychain.hasToken {
                attemptBiometricLogin()
            }
        }
        .onDisappear {
            stopServerDiscovery()
        }
    }

    // MARK: - Header Section

    private var headerSection: some View {
        VStack(spacing: 16) {
            // Kanji logo
            Text("\u{93e1}") // U+93E1 = Mirror
                .font(.system(size: 72))
                .foregroundColor(.crystal.opacity(0.8))
                .accessibilityLabel("Kagami logo")

            Text("Kagami")
                .font(KagamiFont.largeTitle())
                .foregroundColor(.accessibleTextPrimary)

            Text("Sign in to your home")
                .font(KagamiFont.subheadline())
                .foregroundColor(.accessibleTextSecondary)
        }
        .padding(.top, 40)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Kagami. Sign in to your home.")
    }

    // MARK: - Server Section

    private var serverSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Server")
                .font(KagamiFont.headline())
                .foregroundColor(.accessibleTextSecondary)

            HStack(spacing: 12) {
                // Server URL field
                TextField("https://api.awkronos.com", text: $serverURL)
                    .textFieldStyle(KagamiTextFieldStyle())
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .keyboardType(.URL)
                    .textContentType(.URL)
                    .accessibilityLabel("Server URL")
                    .accessibilityHint("Enter your Kagami server address")

                // Discovery button
                Button {
                    startServerDiscovery()
                } label: {
                    ZStack {
                        if isDiscoveringServers {
                            ProgressView()
                                .tint(.crystal)
                        } else {
                            Image(systemName: "antenna.radiowaves.left.and.right")
                                .font(.body)
                                .foregroundColor(.crystal)
                        }
                    }
                    .frame(width: 44, height: 44)
                    .background(Color.voidLight)
                    .cornerRadius(KagamiRadius.sm)
                }
                .accessibleButton(
                    label: "Discover servers",
                    hint: "Scan network for Kagami servers"
                )
                .disabled(isDiscoveringServers)
            }

            if !discoveredServers.isEmpty {
                Button {
                    showServerPicker = true
                } label: {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.safetyOk)
                        Text("\(discoveredServers.count) server\(discoveredServers.count == 1 ? "" : "s") found")
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                    }
                }
                .accessibilityLabel("\(discoveredServers.count) servers discovered. Tap to select.")
            }
        }
    }

    // MARK: - Credentials Section

    private var credentialsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Credentials")
                .font(KagamiFont.headline())
                .foregroundColor(.accessibleTextSecondary)

            // Username
            VStack(alignment: .leading, spacing: 8) {
                Text("Username")
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextTertiary)

                TextField("username", text: $username)
                    .textFieldStyle(KagamiTextFieldStyle())
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .textContentType(.username)
                    .accessibilityLabel("Username")
            }

            // Password
            VStack(alignment: .leading, spacing: 8) {
                Text("Password")
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextTertiary)

                SecureField("password", text: $password)
                    .textFieldStyle(KagamiTextFieldStyle())
                    .textContentType(.password)
                    .accessibilityLabel("Password")
            }
        }
    }

    // MARK: - Actions Section

    private var actionsSection: some View {
        VStack(spacing: KagamiSpacing.md) {
            // Biometric login button (if available)
            if canUseBiometrics {
                Button {
                    attemptBiometricLogin()
                } label: {
                    HStack(spacing: KagamiSpacing.sm) {
                        Image(systemName: biometricType.systemImage)
                            .font(.title2)
                        Text(biometricType.displayName)
                            .font(KagamiFont.headline())
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Color.crystal)
                    .foregroundColor(.void)
                    .cornerRadius(KagamiRadius.md)
                }
                .accessibleButton(
                    label: "Sign in with \(biometricType.displayName)",
                    hint: "Double tap to authenticate with \(biometricType.displayName)"
                )
                .disabled(isLoading)
            }

            // Login button
            Button {
                performLogin()
            } label: {
                HStack {
                    if isLoading {
                        ProgressView()
                            .tint(.void)
                    } else {
                        Text("Sign In")
                            .font(KagamiFont.headline())
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(isFormValid ? (canUseBiometrics ? Color.voidLight : Color.crystal) : Color.crystal.opacity(0.5))
                .foregroundColor(canUseBiometrics ? .crystal : .void)
                .cornerRadius(KagamiRadius.md)
                .overlay(
                    canUseBiometrics ?
                    RoundedRectangle(cornerRadius: KagamiRadius.md)
                        .stroke(Color.crystal.opacity(0.5), lineWidth: 1) : nil
                )
            }
            .disabled(!isFormValid || isLoading)
            .accessibleButton(
                label: "Sign in with password",
                hint: isFormValid ? "Double tap to sign in" : "Fill in all fields to enable"
            )

            // Divider
            HStack {
                Rectangle()
                    .fill(Color.accessibleTextTertiary.opacity(0.3))
                    .frame(height: 1)
                Text("or")
                    .font(KagamiFont.caption())
                    .foregroundColor(.accessibleTextTertiary)
                Rectangle()
                    .fill(Color.accessibleTextTertiary.opacity(0.3))
                    .frame(height: 1)
            }
            .accessibilityHidden(true)

            // Create account button
            Button {
                showCreateAccount = true
            } label: {
                Text("Create Account")
                    .font(KagamiFont.body(weight: .medium))
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Color.voidLight)
                    .foregroundColor(.crystal)
                    .cornerRadius(KagamiRadius.md)
                    .overlay(
                        RoundedRectangle(cornerRadius: KagamiRadius.md)
                            .stroke(Color.crystal.opacity(0.5), lineWidth: 1)
                    )
            }
            .accessibleButton(
                label: "Create account",
                hint: "Double tap to create a new account"
            )
        }
    }

    // MARK: - Footer Section

    private var footerSection: some View {
        VStack(spacing: 8) {
            Text("Safety First. Always.")
                .font(KagamiFont.caption())
                .foregroundColor(.crystal.opacity(0.65))

            Text("Your data stays on your server")
                .font(KagamiFont.caption2())
                .foregroundColor(.accessibleTextTertiary)
        }
        .padding(.top, 32)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Safety first, always. Your data stays on your server.")
    }

    // MARK: - Computed Properties

    private var isFormValid: Bool {
        !serverURL.isEmpty && !username.isEmpty && !password.isEmpty
    }

    // MARK: - Actions

    private func loadSavedServerURL() {
        // Security: Default to HTTPS production URL. Local dev requires explicit config.
        if let savedURL = UserDefaults.standard.string(forKey: "kagamiServerURL") {
            serverURL = savedURL
        } else if let envURL = ProcessInfo.processInfo.environment["KAGAMI_BASE_URL"] {
            serverURL = envURL
        } else {
            serverURL = "https://api.awkronos.com"
        }
    }

    // MARK: - Biometric Authentication

    private func checkBiometricAvailability() {
        let context = LAContext()
        var error: NSError?

        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            switch context.biometryType {
            case .faceID:
                biometricType = .faceID
                canUseBiometrics = KagamiKeychain.hasToken
            case .touchID:
                biometricType = .touchID
                canUseBiometrics = KagamiKeychain.hasToken
            case .opticID:
                biometricType = .opticID
                canUseBiometrics = KagamiKeychain.hasToken
            @unknown default:
                biometricType = .none
                canUseBiometrics = false
            }
        } else {
            biometricType = .none
            canUseBiometrics = false
        }
    }

    private func attemptBiometricLogin() {
        let context = LAContext()
        context.localizedCancelTitle = "Use Password"

        let reason = "Sign in to your Kagami home"

        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, error in
            DispatchQueue.main.async {
                if success {
                    // Biometric succeeded - use stored token
                    if let token = KagamiKeychain.getToken() {
                        handleSuccessfulAuth(token: token)
                    } else {
                        // Token not found - fall back to password
                        errorMessage = "Please sign in with your password"
                        showError = true
                    }
                } else if let error = error as? LAError {
                    switch error.code {
                    case .userCancel, .userFallback:
                        // User chose to use password - do nothing
                        break
                    case .biometryNotAvailable, .biometryNotEnrolled:
                        canUseBiometrics = false
                    default:
                        errorMessage = "Authentication failed: \(error.localizedDescription)"
                        showError = true
                    }
                }
            }
        }
    }

    private func performLogin() {
        guard isFormValid else { return }

        isLoading = true

        Task {
            do {
                // Configure API service with server URL
                appModel.apiService.configure(baseURL: serverURL)

                // Attempt login
                let token = try await appModel.apiService.login(
                    username: username,
                    password: password
                )

                await MainActor.run {
                    handleSuccessfulAuth(token: token)
                }
            } catch let error as KagamiAPIService.AuthError {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                    showError = true
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                    showError = true
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
        }
    }

    private func handleSuccessfulAuth(token: String) {
        // Save server URL
        UserDefaults.standard.set(serverURL, forKey: "kagamiServerURL")

        // Store token securely
        KagamiKeychain.saveToken(token)

        // Update app state
        isLoading = false

        // Haptic feedback
        UINotificationFeedbackGenerator().notificationOccurred(.success)

        // Navigate to main app
        withAnimation(.easeInOut(duration: KagamiMotion.normal)) {
            isAuthenticated = true
        }
    }

    // MARK: - Server Discovery (mDNS)

    private func startServerDiscovery() {
        isDiscoveringServers = true
        discoveredServers = []

        // Create browser for Kagami service type
        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        browser = NWBrowser(
            for: .bonjour(type: "_kagami._tcp", domain: nil),
            using: parameters
        )

        browser?.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("mDNS browser ready")
            case .failed(let error):
                print("mDNS browser failed: \(error)")
                Task { @MainActor in
                    isDiscoveringServers = false
                }
            default:
                break
            }
        }

        browser?.browseResultsChangedHandler = { results, _ in
            Task { @MainActor in
                for result in results {
                    if case .service(let name, let type, let domain, _) = result.endpoint {
                        resolveService(name: name, type: type, domain: domain)
                    }
                }
            }
        }

        browser?.start(queue: .main)

        // Also try common addresses as fallback
        Task {
            await tryCommonAddresses()

            // Stop after 5 seconds
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            await MainActor.run {
                stopServerDiscovery()
            }
        }
    }

    private func resolveService(name: String, type: String, domain: String) {
        // Create connection to resolve the service
        let endpoint = NWEndpoint.service(name: name, type: type, domain: domain, interface: nil)
        let connection = NWConnection(to: endpoint, using: .tcp)

        connection.stateUpdateHandler = { state in
            if case .ready = state {
                if let innerEndpoint = connection.currentPath?.remoteEndpoint,
                   case .hostPort(let host, let port) = innerEndpoint {
                    // Note: Discovered local services use HTTPS with self-signed certs
                    let url = "https://\(host):\(port)"
                    Task { @MainActor in
                        if !discoveredServers.contains(where: { $0.url == url }) {
                            discoveredServers.append(DiscoveredServer(name: name, url: url))
                        }
                    }
                }
                connection.cancel()
            }
        }
        connection.start(queue: .main)
    }

    private func tryCommonAddresses() async {
        // Note: Local addresses use HTTPS with self-signed certs for security
        let candidates = [
            ("kagami.local", "https://kagami.local:8001"),
            ("192.168.1.100", "https://192.168.1.100:8001"),
            ("192.168.1.50", "https://192.168.1.50:8001"),
            ("localhost", "https://localhost:8001"),
        ]

        await withTaskGroup(of: DiscoveredServer?.self) { group in
            for (name, url) in candidates {
                group.addTask {
                    if await self.testServerConnection(url: url) {
                        return DiscoveredServer(name: name, url: url)
                    }
                    return nil
                }
            }

            for await result in group {
                if let server = result {
                    await MainActor.run {
                        if !discoveredServers.contains(where: { $0.url == server.url }) {
                            discoveredServers.append(server)
                        }
                    }
                }
            }
        }
    }

    private func testServerConnection(url: String) async -> Bool {
        guard let testURL = URL(string: "\(url)/health") else { return false }

        var request = URLRequest(url: testURL)
        request.timeoutInterval = 3

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    private func stopServerDiscovery() {
        browser?.cancel()
        browser = nil
        isDiscoveringServers = false
    }
}

// MARK: - Discovered Server Model

struct DiscoveredServer: Identifiable {
    let id = UUID()
    let name: String
    let url: String
}

// MARK: - Server Picker View

struct ServerPickerView: View {
    let servers: [DiscoveredServer]
    let onSelect: (DiscoveredServer) -> Void

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                ForEach(servers) { server in
                    Button {
                        onSelect(server)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(server.name)
                                    .font(KagamiFont.headline())
                                    .foregroundColor(.accessibleTextPrimary)
                                Text(server.url)
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextSecondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.accessibleTextTertiary)
                        }
                        .padding(.vertical, 8)
                    }
                    .accessibilityLabel("\(server.name) at \(server.url)")
                    .accessibilityHint("Double tap to select this server")
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Select Server")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Create Account View

struct CreateAccountView: View {
    let serverURL: String
    let onAccountCreated: (String) -> Void

    @EnvironmentObject var appModel: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var username: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var confirmPassword: String = ""
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Color.void
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // Header
                        VStack(spacing: 8) {
                            Text("Create Account")
                                .font(KagamiFont.title())
                                .foregroundColor(.accessibleTextPrimary)
                            Text("Join your Kagami home")
                                .font(KagamiFont.subheadline())
                                .foregroundColor(.accessibleTextSecondary)
                        }
                        .padding(.top, 20)

                        // Form
                        VStack(spacing: 16) {
                            // Username
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Username")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                TextField("username", text: $username)
                                    .textFieldStyle(KagamiTextFieldStyle())
                                    .autocapitalization(.none)
                                    .disableAutocorrection(true)
                                    .textContentType(.username)
                            }

                            // Email
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Email")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                TextField("email@example.com", text: $email)
                                    .textFieldStyle(KagamiTextFieldStyle())
                                    .autocapitalization(.none)
                                    .disableAutocorrection(true)
                                    .keyboardType(.emailAddress)
                                    .textContentType(.emailAddress)
                            }

                            // Password
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Password")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                SecureField("password", text: $password)
                                    .textFieldStyle(KagamiTextFieldStyle())
                                    .textContentType(.newPassword)
                            }

                            // Confirm Password
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Confirm Password")
                                    .font(KagamiFont.caption())
                                    .foregroundColor(.accessibleTextTertiary)
                                SecureField("confirm password", text: $confirmPassword)
                                    .textFieldStyle(KagamiTextFieldStyle())
                                    .textContentType(.newPassword)

                                if !confirmPassword.isEmpty && password != confirmPassword {
                                    Text("Passwords do not match")
                                        .font(KagamiFont.caption())
                                        .foregroundColor(.safetyViolation)
                                }
                            }
                        }

                        // Create button
                        Button {
                            createAccount()
                        } label: {
                            HStack {
                                if isLoading {
                                    ProgressView()
                                        .tint(.void)
                                } else {
                                    Text("Create Account")
                                        .font(KagamiFont.headline())
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .frame(height: 50)
                            .background(isFormValid ? Color.crystal : Color.crystal.opacity(0.5))
                            .foregroundColor(.void)
                            .cornerRadius(KagamiRadius.md)
                        }
                        .disabled(!isFormValid || isLoading)
                        .padding(.top, 8)
                    }
                    .padding(24)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.crystal)
                }
            }
        }
        .preferredColorScheme(.dark)
        .alert("Registration Failed", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage)
        }
    }

    private var isFormValid: Bool {
        !username.isEmpty &&
        !email.isEmpty &&
        !password.isEmpty &&
        password == confirmPassword &&
        password.count >= 8
    }

    private func createAccount() {
        guard isFormValid else { return }

        isLoading = true

        Task {
            do {
                appModel.apiService.configure(baseURL: serverURL)

                let token = try await appModel.apiService.register(
                    username: username,
                    email: email,
                    password: password
                )

                await MainActor.run {
                    isLoading = false
                    dismiss()
                    onAccountCreated(token)
                }
            } catch let error as KagamiAPIService.AuthError {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                    showError = true
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                    showError = true
                }
            }
        }
    }
}

// MARK: - Custom Text Field Style

struct KagamiTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .font(KagamiFont.body())
            .padding(14)
            .background(Color.voidLight)
            .foregroundColor(.accessibleTextPrimary)
            .cornerRadius(KagamiRadius.sm)
            .overlay(
                RoundedRectangle(cornerRadius: KagamiRadius.sm)
                    .stroke(Color.crystal.opacity(0.2), lineWidth: 1)
            )
    }
}

// MARK: - Biometric Type

/// Enum representing available biometric authentication types
enum BiometricType {
    case none
    case touchID
    case faceID
    case opticID  // Vision Pro

    var displayName: String {
        switch self {
        case .none: return "Biometric"
        case .touchID: return "Touch ID"
        case .faceID: return "Face ID"
        case .opticID: return "Optic ID"
        }
    }

    var systemImage: String {
        switch self {
        case .none: return "person.badge.key"
        case .touchID: return "touchid"
        case .faceID: return "faceid"
        case .opticID: return "opticid"
        }
    }
}

// MARK: - Keychain Helper
//
// Note: KagamiKeychain is now defined in Services/KeychainService.swift
// It provides secure token storage with additional features like
// refresh tokens and username storage.

// MARK: - Preview

#Preview("Login View") {
    LoginView(isAuthenticated: .constant(false))
        .environmentObject(AppModel())
}

#Preview("Create Account") {
    CreateAccountView(
        serverURL: "https://api.awkronos.com",
        onAccountCreated: { _ in }
    )
    .environmentObject(AppModel())
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
