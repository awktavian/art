//
// VolumetricDataVisualization.swift -- 3D Data Visualizations for visionOS
//
// Kagami Vision -- Volumetric home data display
//
// Colony: Crystal (e7) -- Verification
//
// Per KAGAMI_REDESIGN_PLAN.md: Create volumetric data visualizations
//
// Features:
// - 3D room layout visualization
// - Floating sensor data displays
// - Energy flow visualization
// - Temperature gradient volumes
// - Occupancy heat maps
// - Real-time data updates
// - Interactive 3D controls
//
// h(x) >= 0. Always.
//

import SwiftUI
import RealityKit

// MARK: - Volumetric Room View

/// 3D visualization of home rooms with sensor data
struct VolumetricRoomView: View {
    let rooms: [RoomVolumetricData]
    let selectedRoomId: String?
    let onRoomSelect: (String) -> Void

    @State private var rotationAngle: Float = 0
    @State private var scale: Float = 1.0

    var body: some View {
        RealityView { content in
            // Create room entities
            for room in rooms {
                let entity = createRoomEntity(room)
                content.add(entity)
            }

            // Add ambient lighting
            let light = PointLight()
            light.light.intensity = 1000
            light.position = SIMD3<Float>(0, 2, 0)
            content.add(light)

        } update: { content in
            // Update room entities with new data
            for room in rooms {
                if let entity = content.entities.first(where: { $0.name == room.id }) {
                    updateRoomEntity(entity, with: room, isSelected: room.id == selectedRoomId)
                }
            }
        }
        .gesture(
            RotateGesture()
                .onChanged { value in
                    rotationAngle = Float(value.rotation.degrees)
                }
        )
        .gesture(
            MagnifyGesture()
                .onChanged { value in
                    scale = Float(value.magnification)
                }
        )
        .accessibilityElement(children: .contain)
        .accessibilityLabel("3D home visualization with \(rooms.count) rooms")
    }

    private func createRoomEntity(_ room: RoomVolumetricData) -> Entity {
        let entity = Entity()
        entity.name = room.id

        // Room box
        let roomMesh = MeshResource.generateBox(
            size: SIMD3<Float>(room.size.width, room.size.height, room.size.depth)
        )

        // Material based on light level
        var material = SimpleMaterial()
        material.color = .init(tint: room.lightLevel > 0 ? .yellow.withAlphaComponent(CGFloat(room.lightLevel) / 100) : .gray.withAlphaComponent(0.3))

        let modelComponent = ModelComponent(mesh: roomMesh, materials: [material])
        entity.components.set(modelComponent)

        // Position
        entity.position = room.position

        // Add occupancy indicator
        if room.isOccupied {
            let occupancyIndicator = createOccupancyIndicator()
            occupancyIndicator.position = SIMD3<Float>(0, room.size.height / 2 + 0.1, 0)
            entity.addChild(occupancyIndicator)
        }

        // Add temperature visualization if available
        if let temp = room.temperature {
            let tempIndicator = createTemperatureIndicator(temp)
            tempIndicator.position = SIMD3<Float>(room.size.width / 2, 0, 0)
            entity.addChild(tempIndicator)
        }

        return entity
    }

    private func createOccupancyIndicator() -> Entity {
        let entity = Entity()

        // Small glowing sphere
        let mesh = MeshResource.generateSphere(radius: 0.05)
        var material = SimpleMaterial()
        material.color = .init(tint: .green)

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        return entity
    }

    private func createTemperatureIndicator(_ temperature: Double) -> Entity {
        let entity = Entity()

        // Color based on temperature
        let tempColor: UIColor
        if temperature < 18 { tempColor = .blue }
        else if temperature < 22 { tempColor = .green }
        else if temperature < 26 { tempColor = .yellow }
        else { tempColor = .red }

        let mesh = MeshResource.generateSphere(radius: 0.03)
        var material = SimpleMaterial()
        material.color = .init(tint: tempColor)

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        return entity
    }

    private func updateRoomEntity(_ entity: Entity, with room: RoomVolumetricData, isSelected: Bool) {
        // Update selection state
        entity.transform.scale = isSelected ? SIMD3<Float>(1.1, 1.1, 1.1) : SIMD3<Float>(1, 1, 1)

        // Update material for light level
        if var model = entity.components[ModelComponent.self] {
            var material = SimpleMaterial()
            let alpha = room.lightLevel > 0 ? CGFloat(room.lightLevel) / 100 : 0.3
            material.color = .init(tint: room.lightLevel > 0 ? .yellow.withAlphaComponent(alpha) : .gray.withAlphaComponent(0.3))
            model.materials = [material]
            entity.components.set(model)
        }
    }
}

// MARK: - Room Data Model

struct RoomVolumetricData: Identifiable {
    let id: String
    let name: String
    let position: SIMD3<Float>
    let size: RoomSize
    var lightLevel: Int
    var isOccupied: Bool
    var temperature: Double?
    var humidity: Double?
    var co2Level: Double?

    struct RoomSize {
        let width: Float
        let height: Float
        let depth: Float
    }
}

// MARK: - Sensor Data Floating Display

/// Floating 3D display of sensor data
struct SensorDataVolumetricView: View {
    let sensors: [SensorVolumetricData]
    @State private var selectedSensor: String?

    var body: some View {
        RealityView { content in
            for sensor in sensors {
                let entity = createSensorEntity(sensor)
                content.add(entity)
            }
        } update: { content in
            for sensor in sensors {
                if let entity = content.entities.first(where: { $0.name == sensor.id }) {
                    updateSensorEntity(entity, with: sensor)
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Floating sensor displays showing \(sensors.count) sensors")
    }

    private func createSensorEntity(_ sensor: SensorVolumetricData) -> Entity {
        let entity = Entity()
        entity.name = sensor.id
        entity.position = sensor.position

        // Create floating panel
        let panelMesh = MeshResource.generatePlane(width: 0.2, height: 0.15)
        var material = SimpleMaterial()
        material.color = .init(tint: .black.withAlphaComponent(0.8))

        entity.components.set(ModelComponent(mesh: panelMesh, materials: [material]))

        // Make it face the user
        entity.look(at: SIMD3<Float>(0, 0, 0), from: sensor.position, relativeTo: nil)

        return entity
    }

    private func updateSensorEntity(_ entity: Entity, with sensor: SensorVolumetricData) {
        // Entities would be updated with actual text rendering
        // In practice, you'd use a TextModel or attachment
    }
}

struct SensorVolumetricData: Identifiable {
    let id: String
    let name: String
    let type: SensorType
    let value: Double
    let unit: String
    let position: SIMD3<Float>
    let status: SensorStatus

    enum SensorType {
        case temperature
        case humidity
        case co2
        case motion
        case light
        case power
    }

    enum SensorStatus {
        case normal
        case warning
        case alert
    }
}

// MARK: - Energy Flow Visualization

/// 3D visualization of energy flow through the home
struct EnergyFlowVolumetricView: View {
    let sources: [EnergySource]
    let consumers: [EnergyConsumer]
    let flows: [EnergyFlow]

    var body: some View {
        RealityView { content in
            // Create energy sources (solar, grid, battery)
            for source in sources {
                let entity = createEnergySourceEntity(source)
                content.add(entity)
            }

            // Create consumers (rooms, appliances)
            for consumer in consumers {
                let entity = createEnergyConsumerEntity(consumer)
                content.add(entity)
            }

            // Create flow lines
            for flow in flows {
                let entity = createEnergyFlowEntity(flow)
                content.add(entity)
            }
        }
        .accessibilityLabel("Energy flow visualization showing \(sources.count) sources and \(consumers.count) consumers")
    }

    private func createEnergySourceEntity(_ source: EnergySource) -> Entity {
        let entity = Entity()
        entity.name = source.id
        entity.position = source.position

        // Icon representation
        let mesh = MeshResource.generateBox(size: 0.15)
        var material = SimpleMaterial()

        switch source.type {
        case .solar:
            material.color = .init(tint: .yellow)
        case .grid:
            material.color = .init(tint: .blue)
        case .battery:
            material.color = .init(tint: .green)
        }

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        return entity
    }

    private func createEnergyConsumerEntity(_ consumer: EnergyConsumer) -> Entity {
        let entity = Entity()
        entity.name = consumer.id
        entity.position = consumer.position

        let mesh = MeshResource.generateSphere(radius: 0.08)
        var material = SimpleMaterial()

        // Color based on consumption level
        let intensity = min(1.0, consumer.currentPower / consumer.maxPower)
        material.color = .init(tint: UIColor(red: intensity, green: 0.3, blue: 0.8 - intensity * 0.5, alpha: 1.0))

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        return entity
    }

    private func createEnergyFlowEntity(_ flow: EnergyFlow) -> Entity {
        let entity = Entity()

        // Create a line from source to consumer
        // In practice, you'd use particle systems or custom geometry
        let mesh = MeshResource.generateCylinder(height: flow.distance, radius: 0.01)
        var material = SimpleMaterial()
        material.color = .init(tint: .cyan.withAlphaComponent(0.6))

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))

        // Position at midpoint
        entity.position = (flow.sourcePosition + flow.consumerPosition) / 2

        // Rotate to connect points
        let direction = normalize(flow.consumerPosition - flow.sourcePosition)
        entity.look(at: flow.consumerPosition, from: entity.position, relativeTo: nil)

        return entity
    }
}

struct EnergySource: Identifiable {
    let id: String
    let name: String
    let type: SourceType
    let position: SIMD3<Float>
    var currentOutput: Double  // Watts
    var maxOutput: Double

    enum SourceType {
        case solar
        case grid
        case battery
    }
}

struct EnergyConsumer: Identifiable {
    let id: String
    let name: String
    let position: SIMD3<Float>
    var currentPower: Double  // Watts
    var maxPower: Double
}

struct EnergyFlow {
    let sourceId: String
    let consumerId: String
    let sourcePosition: SIMD3<Float>
    let consumerPosition: SIMD3<Float>
    var power: Double  // Watts

    var distance: Float {
        simd_length(consumerPosition - sourcePosition)
    }
}

// MARK: - Temperature Gradient Volume

/// 3D temperature gradient visualization
struct TemperatureGradientVolumetricView: View {
    let temperatureData: [[Double]]  // 3D grid of temperatures
    let minTemp: Double
    let maxTemp: Double
    let gridSize: SIMD3<Int>

    var body: some View {
        RealityView { content in
            // Create voxel-based temperature visualization
            for x in 0..<gridSize.x {
                for y in 0..<gridSize.y {
                    for z in 0..<gridSize.z {
                        guard x < temperatureData.count,
                              y < temperatureData[x].count else { continue }

                        let temp = temperatureData[x][y]
                        let normalizedTemp = (temp - minTemp) / (maxTemp - minTemp)

                        // Only render significant temperature gradients
                        guard normalizedTemp > 0.1 else { continue }

                        let entity = createTemperatureVoxel(
                            position: SIMD3<Float>(Float(x) * 0.1, Float(y) * 0.1, Float(z) * 0.1),
                            normalizedTemp: normalizedTemp
                        )
                        content.add(entity)
                    }
                }
            }
        }
        .accessibilityLabel("Temperature gradient visualization from \(Int(minTemp)) to \(Int(maxTemp)) degrees")
    }

    private func createTemperatureVoxel(position: SIMD3<Float>, normalizedTemp: Double) -> Entity {
        let entity = Entity()
        entity.position = position

        let mesh = MeshResource.generateBox(size: 0.08)
        var material = SimpleMaterial()

        // Blue (cold) to Red (hot) gradient
        let color = UIColor(
            red: normalizedTemp,
            green: 0.2,
            blue: 1.0 - normalizedTemp,
            alpha: normalizedTemp * 0.5 + 0.1
        )
        material.color = .init(tint: color)

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        return entity
    }
}

// MARK: - Safety Score Volumetric Display

/// 3D visualization of the h(x) safety barrier
struct SafetyScoreVolumetricView: View {
    let safetyScore: Double
    @State private var pulsePhase: Float = 0

    var body: some View {
        TimelineView(.animation) { timeline in
            let phase = Float(timeline.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 4.0) / 4.0)

            RealityView { content in
                // Create safety sphere
                let entity = createSafetySphere()
                entity.name = "safety_sphere"
                content.add(entity)

            } update: { content in
                if let entity = content.entities.first(where: { $0.name == "safety_sphere" }) {
                    updateSafetySphere(entity, score: safetyScore, phase: phase)
                }
            }
        }
        .accessibilityLabel("Safety score display at \(Int(safetyScore * 100)) percent")
    }

    private func createSafetySphere() -> Entity {
        let entity = Entity()

        // Outer sphere (barrier visualization)
        let outerMesh = MeshResource.generateSphere(radius: 0.3)
        var outerMaterial = SimpleMaterial()
        outerMaterial.color = .init(tint: .green.withAlphaComponent(0.3))

        let outerEntity = Entity()
        outerEntity.components.set(ModelComponent(mesh: outerMesh, materials: [outerMaterial]))
        outerEntity.name = "outer"
        entity.addChild(outerEntity)

        // Inner core
        let innerMesh = MeshResource.generateSphere(radius: 0.1)
        var innerMaterial = SimpleMaterial()
        innerMaterial.color = .init(tint: .white)

        let innerEntity = Entity()
        innerEntity.components.set(ModelComponent(mesh: innerMesh, materials: [innerMaterial]))
        innerEntity.name = "inner"
        entity.addChild(innerEntity)

        return entity
    }

    private func updateSafetySphere(_ entity: Entity, score: Double, phase: Float) {
        // Update outer sphere color based on score
        if let outer = entity.children.first(where: { $0.name == "outer" }) {
            let color: UIColor
            if score >= 0.9 { color = .green.withAlphaComponent(0.3 + Double(phase) * 0.2) }
            else if score >= 0.5 { color = .yellow.withAlphaComponent(0.4 + Double(phase) * 0.2) }
            else { color = .red.withAlphaComponent(0.5 + Double(phase) * 0.3) }

            var material = SimpleMaterial()
            material.color = .init(tint: color)

            if var model = outer.components[ModelComponent.self] {
                model.materials = [material]
                outer.components.set(model)
            }

            // Pulsing scale
            let pulseScale = 1.0 + Float(phase) * 0.1
            outer.transform.scale = SIMD3<Float>(repeating: pulseScale)
        }

        // Update inner core
        if let inner = entity.children.first(where: { $0.name == "inner" }) {
            // Breathing effect
            let breathScale = 0.9 + Float(score) * 0.2 + sin(phase * .pi * 2) * 0.05
            inner.transform.scale = SIMD3<Float>(repeating: breathScale)
        }
    }
}

// MARK: - Preview

#Preview {
    VolumetricRoomView(
        rooms: [
            RoomVolumetricData(
                id: "living",
                name: "Living Room",
                position: SIMD3<Float>(0, 0, 0),
                size: .init(width: 0.5, height: 0.3, depth: 0.4),
                lightLevel: 75,
                isOccupied: true,
                temperature: 22.5
            ),
            RoomVolumetricData(
                id: "kitchen",
                name: "Kitchen",
                position: SIMD3<Float>(0.6, 0, 0),
                size: .init(width: 0.4, height: 0.3, depth: 0.3),
                lightLevel: 50,
                isOccupied: false,
                temperature: 24.0
            )
        ],
        selectedRoomId: "living",
        onRoomSelect: { _ in }
    )
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Data becomes tangible.
 * The invisible made visible.
 * Understanding through form.
 */
