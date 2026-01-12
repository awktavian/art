//! Kagami Orb Base Station Firmware
//!
//! Main entry point for the ESP32-S3 based base station controller.
//!
//! # Tasks
//!
//! - `height_control_task`: 100Hz control loop for levitation
//! - `wpt_control_task`: Wireless power transfer management
//! - `led_animator_task`: Base LED animation
//! - `communication_task`: WebSocket to hub, protocol with orb
//! - `sensor_monitor_task`: Temperature and presence monitoring

#![no_std]
#![no_main]
#![feature(type_alias_impl_trait)]

use esp_backtrace as _;
use esp_println::println;

use embassy_executor::Spawner;
use embassy_time::{Duration, Timer, Instant};

mod levitation;
mod error;

use levitation::{HeightController, LevitationMode, constants};
use error::BaseResult;

/// Main entry point
#[esp_hal_embassy::main]
async fn main(spawner: Spawner) {
    println!("Kagami Orb Base Station v0.1.0");
    println!("h(x) >= 0 always");
    println!();

    // Initialize ESP32-S3 peripherals
    let peripherals = esp_hal::init(esp_hal::Config::default());

    // Initialize embassy async runtime
    esp_hal_embassy::init(peripherals.TIMG0);

    println!("Hardware initialized");

    // Spawn tasks
    spawner.spawn(height_control_task()).unwrap();
    spawner.spawn(safety_monitor_task()).unwrap();

    // TODO: Add these tasks when HAL is available
    // spawner.spawn(wpt_control_task()).unwrap();
    // spawner.spawn(led_animator_task()).unwrap();
    // spawner.spawn(communication_task()).unwrap();
    // spawner.spawn(sensor_monitor_task()).unwrap();

    println!("Tasks spawned, entering main loop");

    // Main loop - just keep the system alive
    loop {
        Timer::after(Duration::from_secs(10)).await;
        println!("Base station running...");
    }
}

/// Height control task - runs at 100Hz
///
/// This is the core levitation control loop. It reads the Hall sensor,
/// computes the target height based on current mode, and sets the DAC
/// output to command the HCNT module.
#[embassy_executor::task]
async fn height_control_task() {
    println!("Height control task started");

    let mut controller = HeightController::new();
    let mut last_update = Instant::now();

    // Simulated initial state - orb placed on base
    Timer::after(Duration::from_secs(2)).await;
    controller.on_orb_placed();
    println!("Orb placed, starting levitation");

    loop {
        let now = Instant::now();
        let dt = (now - last_update).as_micros() as f32 / 1_000_000.0;
        last_update = now;

        // TODO: Read actual ADC value from Hall sensor
        let adc_value: u16 = 2600; // Simulated ~15mm

        // TODO: Read actual temperature from NTC
        let coil_temp: f32 = 45.0; // Simulated

        // TODO: Read actual power supply status
        let power_ok = true;

        // Run control loop
        match controller.update(adc_value, power_ok, coil_temp) {
            Ok((dac_voltage, wpt_freq)) => {
                // TODO: Write DAC voltage via I2C to MCP4725
                // TODO: Update WPT frequency

                // Log state periodically
                if now.as_millis() % 1000 < 10 {
                    let state = controller.state();
                    println!(
                        "h={:.1}mm v={:.1}mm/s mode={:?} dac={:.2}V",
                        state.height_mm,
                        state.velocity_mm_s,
                        controller.mode(),
                        dac_voltage
                    );
                }
            }
            Err(e) => {
                println!("Control error: {:?}", e);
            }
        }

        // Maintain 100Hz rate
        let elapsed = Instant::now() - now;
        let target_period = Duration::from_millis(constants::CONTROL_PERIOD_MS);
        if elapsed < target_period {
            Timer::after(target_period - elapsed).await;
        }
    }
}

/// Safety monitor task - continuous background monitoring
///
/// Watches for safety violations and triggers emergency procedures
/// independent of the main control loop.
#[embassy_executor::task]
async fn safety_monitor_task() {
    println!("Safety monitor task started");

    loop {
        // TODO: Check power supply voltage
        // TODO: Check temperature sensors
        // TODO: Check Hall sensor validity
        // TODO: Check WPT fault signals

        // Run at 10Hz
        Timer::after(Duration::from_millis(100)).await;
    }
}

// Placeholder tasks for future implementation

/*
#[embassy_executor::task]
async fn wpt_control_task() {
    println!("WPT control task started");

    loop {
        // TODO: Manage bq500215 TX controller
        // TODO: Monitor power transfer efficiency
        // TODO: Handle FOD alerts
        // TODO: Adjust frequency for optimal coupling

        Timer::after(Duration::from_millis(100)).await;
    }
}

#[embassy_executor::task]
async fn led_animator_task() {
    println!("LED animator task started");

    loop {
        // TODO: Animate SK6812 ring based on current mode
        // - Thinking: purple/blue pulse
        // - Ambient: warm white glow
        // - Charging: green pulse
        // - Error: red flash

        // Run at 60Hz for smooth animation
        Timer::after(Duration::from_millis(16)).await;
    }
}

#[embassy_executor::task]
async fn communication_task() {
    println!("Communication task started");

    loop {
        // TODO: WebSocket connection to kagami-hub
        // TODO: Receive commands from orb
        // TODO: Send status updates

        Timer::after(Duration::from_millis(10)).await;
    }
}

#[embassy_executor::task]
async fn sensor_monitor_task() {
    println!("Sensor monitor task started");

    loop {
        // TODO: Read NTC temperature sensors
        // TODO: Read Hall switch for orb presence
        // TODO: Monitor power supply voltage

        Timer::after(Duration::from_millis(500)).await;
    }
}
*/

// Panic handler for no_std environment
#[panic_handler]
fn panic(info: &core::panic::PanicInfo) -> ! {
    println!("PANIC: {:?}", info);
    loop {}
}
