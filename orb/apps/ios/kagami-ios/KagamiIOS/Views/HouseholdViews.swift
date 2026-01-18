//
// HouseholdViews.swift — Household Member Management
//
// Colony: Nexus (e4) — Integration
//
// Per plan: Full household accounts with family/guest profiles
//

import SwiftUI

// MARK: - Household Members View

struct HouseholdMembersView: View {
    @EnvironmentObject var appModel: AppModel
    @State private var members: [HouseholdMemberViewModel] = []
    @State private var isLoading = true
    @State private var selectedMember: HouseholdMemberViewModel?

    var body: some View {
        List {
            // Current user section
            Section("You") {
                if let current = members.first(where: { $0.isCurrentUser }) {
                    MemberRow(member: current, isCurrent: true)
                }
            }

            // Other members section
            if members.filter({ !$0.isCurrentUser }).count > 0 {
                Section("Members") {
                    ForEach(members.filter { !$0.isCurrentUser }) { member in
                        MemberRow(member: member, isCurrent: false)
                            .onTapGesture {
                                selectedMember = member
                            }
                    }
                }
            }

            // Pending invitations
            Section("Pending Invitations") {
                if appModel.pendingInvitations.isEmpty {
                    Text("No pending invitations")
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                } else {
                    ForEach(appModel.pendingInvitations, id: \.email) { invitation in
                        HStack {
                            Image(systemName: "envelope")
                                .foregroundColor(.beacon)
                            Text(invitation.email)
                                .font(KagamiFont.body())
                            Spacer()
                            Text("Pending")
                                .font(KagamiFont.caption())
                                .foregroundColor(.beacon)
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .background(Color.void)
        .scrollContentBackground(.hidden)
        .navigationTitle("Household")
        .refreshable {
            await loadMembers()
        }
        .task {
            await loadMembers()
        }
        .sheet(item: $selectedMember) { member in
            MemberDetailSheet(member: member)
        }
    }

    private func loadMembers() async {
        isLoading = true
        // Load from API
        members = await appModel.apiService.fetchHouseholdMembers()
        isLoading = false
    }
}

// MARK: - Member Row

struct MemberRow: View {
    let member: HouseholdMemberViewModel
    let isCurrent: Bool

    var body: some View {
        HStack(spacing: 12) {
            // Avatar
            ZStack {
                Circle()
                    .fill(member.role.color.opacity(0.2))
                    .frame(width: 44, height: 44)

                Text(member.initials)
                    .font(KagamiFont.body(weight: .semibold))
                    .foregroundColor(member.role.color)
            }

            // Info
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(member.displayName)
                        .font(KagamiFont.body())
                        .foregroundColor(.accessibleTextPrimary)

                    if isCurrent {
                        Text("(You)")
                            .font(KagamiFont.caption())
                            .foregroundColor(.accessibleTextSecondary)
                    }
                }

                Text(member.role.displayName)
                    .font(KagamiFont.caption())
                    .foregroundColor(member.role.color)
            }

            Spacer()

            // Voice profile indicator
            if member.hasVoiceProfile {
                Image(systemName: "waveform")
                    .foregroundColor(.crystal)
                    .accessibilityLabel("Voice profile configured")
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(member.displayName), \(member.role.displayName)\(member.hasVoiceProfile ? ", voice profile configured" : "")")
    }
}

// MARK: - Member Detail Sheet

struct MemberDetailSheet: View {
    let member: HouseholdMemberViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        Text("Name")
                        Spacer()
                        Text(member.displayName)
                            .foregroundColor(.accessibleTextSecondary)
                    }

                    HStack {
                        Text("Role")
                        Spacer()
                        Text(member.role.displayName)
                            .foregroundColor(member.role.color)
                    }

                    HStack {
                        Text("Voice Profile")
                        Spacer()
                        Text(member.hasVoiceProfile ? "Configured" : "Not Set")
                            .foregroundColor(member.hasVoiceProfile ? .grove : .accessibleTextSecondary)
                    }
                }

                if member.role == .owner || member.role == .admin {
                    Section("Permissions") {
                        PermissionRow(title: "Control Devices", allowed: true)
                        PermissionRow(title: "Modify Scenes", allowed: true)
                        PermissionRow(title: "Manage Members", allowed: member.role == .owner)
                        PermissionRow(title: "View History", allowed: true)
                    }
                } else if member.role == .member {
                    Section("Permissions") {
                        PermissionRow(title: "Control Devices", allowed: true)
                        PermissionRow(title: "Modify Scenes", allowed: false)
                        PermissionRow(title: "Manage Members", allowed: false)
                        PermissionRow(title: "View History", allowed: true)
                    }
                } else {
                    Section("Permissions") {
                        PermissionRow(title: "Control Devices", allowed: true)
                        PermissionRow(title: "Modify Scenes", allowed: false)
                        PermissionRow(title: "Manage Members", allowed: false)
                        PermissionRow(title: "View History", allowed: false)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .background(Color.void)
            .scrollContentBackground(.hidden)
            .navigationTitle(member.displayName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct PermissionRow: View {
    let title: String
    let allowed: Bool

    var body: some View {
        HStack {
            Text(title)
                .font(KagamiFont.body())
            Spacer()
            Image(systemName: allowed ? "checkmark.circle.fill" : "xmark.circle")
                .foregroundColor(allowed ? .grove : .accessibleTextSecondary)
        }
    }
}

// MARK: - Invite Member View

struct InviteMemberView: View {
    @EnvironmentObject var appModel: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var email = ""
    @State private var selectedRole: HouseholdRole = .member
    @State private var isInviting = false
    @State private var showSuccess = false
    @State private var errorMessage: String?

    var body: some View {
        Form {
            Section("Invitation Details") {
                TextField("Email Address", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .accessibilityLabel("Email address")
                    .accessibilityHint("Enter the email address of the person to invite")

                Picker("Role", selection: $selectedRole) {
                    ForEach(HouseholdRole.invitableRoles, id: \.self) { role in
                        Text(role.displayName)
                            .tag(role)
                    }
                }
                .accessibilityLabel("Member role")
            }

            Section("Role Permissions") {
                VStack(alignment: .leading, spacing: 8) {
                    Text(selectedRole.description)
                        .font(KagamiFont.caption())
                        .foregroundColor(.accessibleTextSecondary)
                }
            }

            Section {
                Button {
                    sendInvitation()
                } label: {
                    HStack {
                        Spacer()
                        if isInviting {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Send Invitation")
                        }
                        Spacer()
                    }
                }
                .disabled(email.isEmpty || isInviting)
                .listRowBackground(email.isEmpty ? Color.gray : Color.crystal)
                .foregroundColor(.white)
            }

            if let error = errorMessage {
                Section {
                    Text(error)
                        .font(KagamiFont.caption())
                        .foregroundColor(.safetyViolation)
                }
            }
        }
        .background(Color.void)
        .scrollContentBackground(.hidden)
        .navigationTitle("Invite Member")
        .alert("Invitation Sent", isPresented: $showSuccess) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text("An invitation has been sent to \(email)")
        }
    }

    private func sendInvitation() {
        isInviting = true
        errorMessage = nil

        Task {
            let success = await appModel.apiService.sendHouseholdInvitation(
                email: email,
                role: selectedRole
            )

            await MainActor.run {
                isInviting = false
                if success {
                    showSuccess = true
                } else {
                    errorMessage = "Failed to send invitation. Please try again."
                }
            }
        }
    }
}

// MARK: - Household Models

struct HouseholdMemberViewModel: Identifiable {
    let id: String
    let displayName: String
    let email: String
    let role: HouseholdRole
    let hasVoiceProfile: Bool
    let isCurrentUser: Bool

    var initials: String {
        let parts = displayName.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(displayName.prefix(2)).uppercased()
    }
}

enum HouseholdRole: String, CaseIterable {
    case owner
    case admin
    case member
    case guest

    var displayName: String {
        switch self {
        case .owner: return "Owner"
        case .admin: return "Admin"
        case .member: return "Member"
        case .guest: return "Guest"
        }
    }

    var color: Color {
        switch self {
        case .owner: return .spark
        case .admin: return .nexus
        case .member: return .crystal
        case .guest: return .accessibleTextSecondary
        }
    }

    var description: String {
        switch self {
        case .owner: return "Full control of the household, including billing and member management."
        case .admin: return "Can control all devices, create scenes, and manage members."
        case .member: return "Can control devices and activate scenes, but cannot modify them."
        case .guest: return "Limited device control, perfect for temporary visitors."
        }
    }

    static var invitableRoles: [HouseholdRole] {
        [.admin, .member, .guest]
    }
}

struct PendingInvitation {
    let email: String
    let role: HouseholdRole
    let sentAt: Date
}

// MARK: - API Service Extensions

extension KagamiAPIService {
    func fetchHouseholdMembers() async -> [HouseholdMemberViewModel] {
        // TODO: Implement actual API call
        // For now, return demo data
        return [
            HouseholdMemberViewModel(
                id: "1",
                displayName: "Tim",
                email: "tim@example.com",
                role: .owner,
                hasVoiceProfile: true,
                isCurrentUser: true
            )
        ]
    }

    func sendHouseholdInvitation(email: String, role: HouseholdRole) async -> Bool {
        // TODO: Implement actual API call
        // Simulate network delay
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        return true
    }
}

// MARK: - App Model Extensions

// Note: householdMemberCount is defined in ContentView.swift

extension AppModel {
    var pendingInvitations: [PendingInvitation] {
        // TODO: Track actual pending invitations
        []
    }
}

/*
 * 鏡
 * Household accounts enable personalization.
 */
