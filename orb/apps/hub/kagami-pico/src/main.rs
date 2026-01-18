//! 鏡 Kagami Pico — Real-Time Coprocessor
//!
//! Embassy-based RTOS firmware for the Raspberry Pi Pico (RP2040).
//! Provides deterministic, microsecond-precise control of:
//!
//! - LED Ring: 7 WS2812 LEDs via PIO (60fps animations)
//! - Audio I2S: Sample-accurate microphone input via DMA
//! - Button Input: Low-latency GPIO interrupts
//!
//! Communicates with the main Kagami Hub (Raspberry Pi) via UART.
//!
//! Colony: All seven, unified through e₀
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

#![no_std]
#![no_main]

use defmt::*;
use embassy_executor::Spawner;
use embassy_rp::bind_interrupts;
use embassy_rp::gpio::{Input, Level, Output, Pull};
use embassy_rp::peripherals::{PIO0, UART0};
use embassy_rp::pio::{InterruptHandler as PioInterruptHandler, Pio};
use embassy_rp::uart::{self, BufferedInterruptHandler, BufferedUart, Config as UartConfig};
use embassy_sync::blocking_mutex::raw::ThreadModeRawMutex;
use embassy_sync::channel::Channel;
use embassy_time::{Duration, Ticker, Timer};
use static_cell::StaticCell;
use {defmt_rtt as _, panic_probe as _};

mod led_ring;
mod protocol;

use led_ring::{AnimationPattern, LedRing};
use protocol::{Command, Response, parse_command, encode_response};

// ============================================================================
// Interrupt Bindings
// ============================================================================

bind_interrupts!(struct Irqs {
    PIO0_IRQ_0 => PioInterruptHandler<PIO0>;
    UART0_IRQ => BufferedInterruptHandler<UART0>;
});

// ============================================================================
// Global State
// ============================================================================

/// Command channel from UART to LED task
static COMMAND_CHANNEL: Channel<ThreadModeRawMutex, Command, 16> = Channel::new();

/// Response channel from LED task to UART
static RESPONSE_CHANNEL: Channel<ThreadModeRawMutex, Response, 16> = Channel::new();

// ============================================================================
// Main Entry Point
// ============================================================================

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    info!("鏡 Kagami Pico starting...");

    // Initialize peripherals
    let p = embassy_rp::init(Default::default());

    // ========================================================================
    // UART Setup (for Pi communication)
    // ========================================================================

    static TX_BUF: StaticCell<[u8; 256]> = StaticCell::new();
    static RX_BUF: StaticCell<[u8; 256]> = StaticCell::new();
    let tx_buf = &mut TX_BUF.init([0; 256])[..];
    let rx_buf = &mut RX_BUF.init([0; 256])[..];

    let mut uart_config = UartConfig::default();
    uart_config.baudrate = 115200;

    let uart = BufferedUart::new(
        p.UART0,
        Irqs,
        p.PIN_0,  // TX
        p.PIN_1,  // RX
        tx_buf,
        rx_buf,
        uart_config,
    );

    // ========================================================================
    // PIO Setup (for WS2812 LED ring)
    // ========================================================================

    let Pio { mut common, sm0, .. } = Pio::new(p.PIO0, Irqs);

    // ========================================================================
    // Button Input (GPIO with interrupt)
    // ========================================================================

    let button = Input::new(p.PIN_15, Pull::Up);

    // ========================================================================
    // Status LED (onboard LED for debugging)
    // ========================================================================

    let led = Output::new(p.PIN_25, Level::Low);

    // ========================================================================
    // Spawn Tasks
    // ========================================================================

    // LED ring animation task (60fps, deterministic)
    spawner.spawn(led_ring_task(common, sm0, p.PIN_16)).unwrap();

    // UART communication task
    spawner.spawn(uart_task(uart)).unwrap();

    // Button handler task
    spawner.spawn(button_task(button)).unwrap();

    // Status LED heartbeat
    spawner.spawn(heartbeat_task(led)).unwrap();

    info!("✓ All tasks spawned");

    // Main loop just keeps the executor running
    loop {
        Timer::after(Duration::from_secs(3600)).await;
    }
}

// ============================================================================
// LED Ring Task (60fps, real-time)
// ============================================================================

#[embassy_executor::task]
async fn led_ring_task(
    common: embassy_rp::pio::Common<'static, PIO0>,
    sm: embassy_rp::pio::StateMachine<'static, PIO0, 0>,
    pin: embassy_rp::peripherals::PIN_16,
) {
    info!("LED ring task starting...");

    let mut ring = LedRing::new(common, sm, pin);
    let mut ticker = Ticker::every(Duration::from_hz(60)); // 60fps

    loop {
        // Check for new commands (non-blocking)
        if let Ok(cmd) = COMMAND_CHANNEL.try_receive() {
            match cmd {
                Command::SetPattern { pattern } => {
                    info!("Setting pattern: {}", pattern);
                    ring.set_pattern(AnimationPattern::from_u8(pattern));
                }
                Command::SetBrightness { level } => {
                    info!("Setting brightness: {}", level);
                    ring.set_brightness(level);
                }
                Command::SetColor { r, g, b } => {
                    info!("Setting color: ({}, {}, {})", r, g, b);
                    ring.set_override_color(Some((r, g, b)));
                }
                Command::Ping => {
                    info!("Ping received");
                    let _ = RESPONSE_CHANNEL.try_send(Response::Pong);
                }
                Command::GetStatus => {
                    let _ = RESPONSE_CHANNEL.try_send(Response::Status {
                        pattern: ring.current_pattern() as u8,
                        brightness: ring.brightness(),
                        frame_count: ring.frame_count(),
                    });
                }
            }
        }

        // Render next frame
        ring.render_frame();

        // Wait for next frame tick (16.67ms for 60fps)
        ticker.next().await;
    }
}

// ============================================================================
// UART Communication Task
// ============================================================================

#[embassy_executor::task]
async fn uart_task(mut uart: BufferedUart<'static, UART0>) {
    info!("UART task starting...");

    let mut rx_buf = [0u8; 64];
    let mut rx_pos = 0;

    loop {
        // Read incoming bytes
        let mut byte = [0u8; 1];
        match embedded_io_async::Read::read(&mut uart, &mut byte).await {
            Ok(1) => {
                rx_buf[rx_pos] = byte[0];
                rx_pos += 1;

                // Check for command terminator (newline)
                if byte[0] == b'\n' || rx_pos >= rx_buf.len() - 1 {
                    if let Some(cmd) = parse_command(&rx_buf[..rx_pos]) {
                        let _ = COMMAND_CHANNEL.try_send(cmd);
                    }
                    rx_pos = 0;
                }
            }
            Ok(_) => {}
            Err(_) => {
                Timer::after(Duration::from_millis(10)).await;
            }
        }

        // Send any pending responses
        if let Ok(response) = RESPONSE_CHANNEL.try_receive() {
            let encoded = encode_response(&response);
            let _ = embedded_io_async::Write::write_all(&mut uart, encoded.as_bytes()).await;
            let _ = embedded_io_async::Write::write_all(&mut uart, b"\n").await;
        }
    }
}

// ============================================================================
// Button Task
// ============================================================================

#[embassy_executor::task]
async fn button_task(mut button: Input<'static>) {
    info!("Button task starting...");

    loop {
        // Wait for button press (falling edge)
        button.wait_for_falling_edge().await;
        info!("Button pressed!");

        // Send button event to response channel
        let _ = RESPONSE_CHANNEL.try_send(Response::ButtonPressed);

        // Debounce
        Timer::after(Duration::from_millis(50)).await;

        // Wait for release
        button.wait_for_rising_edge().await;

        // Debounce
        Timer::after(Duration::from_millis(50)).await;
    }
}

// ============================================================================
// Heartbeat Task (status LED)
// ============================================================================

#[embassy_executor::task]
async fn heartbeat_task(mut led: Output<'static>) {
    info!("Heartbeat task starting...");

    loop {
        led.set_high();
        Timer::after(Duration::from_millis(100)).await;
        led.set_low();
        Timer::after(Duration::from_millis(900)).await;
    }
}

/*
 * 鏡
 * Real-time through Embassy. Deterministic through PIO.
 * The coprocessor handles what Linux cannot.
 *
 * h(x) ≥ 0. Always.
 */
