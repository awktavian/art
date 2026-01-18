//
// ContentView.swift — Legacy compatibility
//
// Redirects to the new spatial intelligence system.
// h(x) ≥ 0. Always.
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var kagami: KagamiSpatialIntelligence
    
    var body: some View {
        CompactControlView()
            .environmentObject(kagami)
    }
}

#Preview(windowStyle: .plain) {
    ContentView()
        .environmentObject(KagamiSpatialIntelligence())
}
