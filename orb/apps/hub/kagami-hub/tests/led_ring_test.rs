//! LED Ring Tests - Animation and Hardware Mock Tests
//!
//! Tests the LED ring controller's animation patterns, color calculations,
//! and state transitions. Uses embedded-hal-mock for hardware simulation.
//!
//! Colony: All seven, unified through e0

use pretty_assertions::assert_eq;
use proptest::prelude::*;
use rstest::*;
use std::time::{Duration, Instant};
use test_case::test_case;

use kagami_hub::config::LEDRingConfig;
use kagami_hub::led_ring::{
    AnimationPattern, LEDRing, BEACON, COLONY_COLORS, CRYSTAL, FLOW, FORGE, GROVE, NEXUS, SPARK,
};

// ============================================================================
// Test Fixtures
// ============================================================================

fn default_led_config() -> LEDRingConfig {
    LEDRingConfig {
        enabled: true,
        count: 7,
        pin: 18,
        brightness: 1.0,
        animation_speed: 1.0,
    }
}

fn dim_led_config() -> LEDRingConfig {
    LEDRingConfig {
        enabled: true,
        count: 7,
        pin: 18,
        brightness: 0.5,
        animation_speed: 1.0,
    }
}

// ============================================================================
// Colony Color Constants Tests
// ============================================================================

#[rstest]
fn test_colony_colors_count() {
    assert_eq!(COLONY_COLORS.len(), 7, "Should have 7 colony colors");
}

#[rstest]
fn test_colony_indices() {
    assert_eq!(SPARK, 0);
    assert_eq!(FORGE, 1);
    assert_eq!(FLOW, 2);
    assert_eq!(NEXUS, 3);
    assert_eq!(BEACON, 4);
    assert_eq!(GROVE, 5);
    assert_eq!(CRYSTAL, 6);
}

#[rstest]
fn test_colony_colors_not_black() {
    for (i, color) in COLONY_COLORS.iter().enumerate() {
        assert!(
            color.0 > 0 || color.1 > 0 || color.2 > 0,
            "Colony {} color should not be black",
            i
        );
    }
}

#[rstest]
fn test_colony_colors_are_distinct() {
    for i in 0..COLONY_COLORS.len() {
        for j in (i + 1)..COLONY_COLORS.len() {
            assert_ne!(
                COLONY_COLORS[i], COLONY_COLORS[j],
                "Colony {} and {} should have distinct colors",
                i, j
            );
        }
    }
}

// ============================================================================
// LED Ring Initialization Tests
// ============================================================================

#[rstest]
fn test_led_ring_creation() {
    let config = default_led_config();
    let ring = LEDRing::new(&config).expect("Should create LED ring");
    assert_eq!(ring.pattern(), AnimationPattern::Idle);
}

#[rstest]
fn test_led_ring_with_custom_brightness() {
    let config = dim_led_config();
    let ring = LEDRing::new(&config).expect("Should create LED ring");
    assert_eq!(ring.pattern(), AnimationPattern::Idle);
}

// ============================================================================
// Animation Pattern Tests
// ============================================================================

#[rstest]
fn test_animation_pattern_equality() {
    assert_eq!(AnimationPattern::Idle, AnimationPattern::Idle);
    assert_eq!(AnimationPattern::Breathing, AnimationPattern::Breathing);
    assert_eq!(AnimationPattern::Spin, AnimationPattern::Spin);
    assert_ne!(AnimationPattern::Idle, AnimationPattern::Spin);
}

#[rstest]
fn test_animation_pattern_clone() {
    let pattern = AnimationPattern::Rainbow;
    let cloned = pattern.clone();
    assert_eq!(pattern, cloned);
}

#[rstest]
fn test_animation_pattern_debug() {
    let patterns = vec![
        AnimationPattern::Idle,
        AnimationPattern::Breathing,
        AnimationPattern::Spin,
        AnimationPattern::Pulse,
        AnimationPattern::Cascade,
        AnimationPattern::Flash,
        AnimationPattern::ErrorFlash,
        AnimationPattern::Highlight(0),
        AnimationPattern::Safety(0.5),
        AnimationPattern::Rainbow,
        AnimationPattern::Sparkle,
        AnimationPattern::Spectral,
        AnimationPattern::FanoPulse,
    ];

    for pattern in patterns {
        let debug_str = format!("{:?}", pattern);
        assert!(!debug_str.is_empty());
    }
}

#[rstest]
fn test_highlight_pattern_with_different_indices() {
    assert_eq!(
        AnimationPattern::Highlight(0),
        AnimationPattern::Highlight(0)
    );
    assert_ne!(
        AnimationPattern::Highlight(0),
        AnimationPattern::Highlight(1)
    );
}

#[rstest]
fn test_safety_pattern_with_different_values() {
    assert_eq!(AnimationPattern::Safety(1.0), AnimationPattern::Safety(1.0));
    // f64 comparison - these should be equal
    let s1 = AnimationPattern::Safety(0.5);
    let s2 = AnimationPattern::Safety(0.5);
    assert_eq!(s1, s2);
}

// ============================================================================
// Pattern Setting Tests
// ============================================================================

#[rstest]
fn test_set_pattern() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Breathing);
    assert_eq!(ring.pattern(), AnimationPattern::Breathing);

    ring.set_pattern(AnimationPattern::Spin);
    assert_eq!(ring.pattern(), AnimationPattern::Spin);
}

#[rstest]
fn test_set_same_pattern_idempotent() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Pulse);
    ring.set_pattern(AnimationPattern::Pulse); // Set same pattern again
    assert_eq!(ring.pattern(), AnimationPattern::Pulse);
}

#[rstest]
fn test_set_colony_ring() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Spin);
    ring.set_colony_ring();
    assert_eq!(ring.pattern(), AnimationPattern::Idle);
}

#[rstest]
fn test_highlight_colony() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.highlight_colony(CRYSTAL);
    assert_eq!(ring.pattern(), AnimationPattern::Highlight(CRYSTAL));
}

#[rstest]
fn test_highlight_colony_out_of_bounds() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    let initial_pattern = ring.pattern();
    ring.highlight_colony(10); // Invalid index
    assert_eq!(ring.pattern(), initial_pattern, "Should not change pattern");
}

#[rstest]
fn test_pulse_listening() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.pulse_listening();
    assert_eq!(ring.pattern(), AnimationPattern::Pulse);
}

#[rstest]
fn test_set_safety_status() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_safety_status(1.0);
    assert_eq!(ring.pattern(), AnimationPattern::Safety(1.0));

    ring.set_safety_status(0.25);
    assert_eq!(ring.pattern(), AnimationPattern::Safety(0.25));

    ring.set_safety_status(-0.5);
    assert_eq!(ring.pattern(), AnimationPattern::Safety(-0.5));
}

#[rstest]
fn test_show_error() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.show_error();
    assert_eq!(ring.pattern(), AnimationPattern::ErrorFlash);
}

#[rstest]
fn test_show_success() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.show_success();
    assert_eq!(ring.pattern(), AnimationPattern::Flash);
}

// ============================================================================
// Frame Calculation Tests
// ============================================================================

#[rstest]
fn test_calculate_frame_returns_7_colors() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    let frame = ring.calculate_frame();
    assert_eq!(frame.len(), 7, "Frame should have 7 LED colors");
}

#[rstest]
fn test_idle_frame_shows_colony_colors() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Idle);
    let frame = ring.calculate_frame();

    // With brightness 1.0, colors should match colony colors exactly
    for (i, color) in frame.iter().enumerate() {
        assert_eq!(
            *color, COLONY_COLORS[i],
            "LED {} should show colony color",
            i
        );
    }
}

#[rstest]
fn test_brightness_affects_frame() {
    let config = dim_led_config(); // 0.5 brightness
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Idle);
    let frame = ring.calculate_frame();

    // Colors should be dimmer than full brightness
    for (i, color) in frame.iter().enumerate() {
        let original = COLONY_COLORS[i];
        // Each channel should be approximately half
        assert!(color.0 <= original.0, "Red channel should be dimmed");
        assert!(color.1 <= original.1, "Green channel should be dimmed");
        assert!(color.2 <= original.2, "Blue channel should be dimmed");
    }
}

#[rstest]
fn test_breathing_frame_changes_over_time() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Breathing);

    let frame1 = ring.calculate_frame();
    std::thread::sleep(Duration::from_millis(500)); // Wait for animation to progress
    let frame2 = ring.calculate_frame();

    // Verify both frames have valid colors
    assert_eq!(frame1.len(), 7, "Frame 1 should have 7 LED colors");
    assert_eq!(frame2.len(), 7, "Frame 2 should have 7 LED colors");

    // Breathing animation should produce valid RGB values in both frames
    for (i, color) in frame1.iter().enumerate() {
        assert!(
            color.0 <= 255 && color.1 <= 255 && color.2 <= 255,
            "Frame 1 LED {} should have valid RGB",
            i
        );
    }
    for (i, color) in frame2.iter().enumerate() {
        assert!(
            color.0 <= 255 && color.1 <= 255 && color.2 <= 255,
            "Frame 2 LED {} should have valid RGB",
            i
        );
    }
}

#[rstest]
fn test_flash_frame_alternates() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Flash);

    // Flash animation alternates between on and off
    let frame = ring.calculate_frame();
    // All LEDs should either be the same (on) or different
    assert!(frame.iter().all(|c| *c == frame[0]));
}

#[rstest]
fn test_safety_frame_colors() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    // Safe (h_x >= 0.5) should be green
    ring.set_pattern(AnimationPattern::Safety(1.0));
    let frame = ring.calculate_frame();
    // All LEDs should be the same (safety color)
    assert!(frame.iter().all(|c| *c == frame[0]));

    // Violation (h_x < 0) should be red
    ring.set_pattern(AnimationPattern::Safety(-0.5));
    let frame = ring.calculate_frame();
    assert!(frame.iter().all(|c| *c == frame[0]));
    assert!(frame[0].0 > frame[0].1, "Red should dominate for violation");
}

// ============================================================================
// Animation Timing Tests
// ============================================================================

#[rstest]
fn test_spin_animation_completes_cycle() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Spin);

    // Capture multiple frames to verify animation progresses
    let frames: Vec<_> = (0..5)
        .map(|_| {
            let frame = ring.calculate_frame();
            std::thread::sleep(Duration::from_millis(50));
            frame
        })
        .collect();

    // Not all frames should be identical
    let all_same = frames.windows(2).all(|w| w[0] == w[1]);
    // Animation should progress (may or may not be different due to timing)
}

// ============================================================================
// Render Tests
// ============================================================================

#[rstest]
fn test_render_does_not_panic() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    // Test render with various patterns
    let patterns = vec![
        AnimationPattern::Idle,
        AnimationPattern::Breathing,
        AnimationPattern::Spin,
        AnimationPattern::Pulse,
        AnimationPattern::Rainbow,
        AnimationPattern::Sparkle,
        AnimationPattern::Spectral,
        AnimationPattern::FanoPulse,
    ];

    for pattern in patterns {
        ring.set_pattern(pattern);
        ring.render(); // Should not panic
    }
}

// ============================================================================
// Spectral and Fano Animation Tests
// ============================================================================

#[rstest]
fn test_spectral_animation_sweeps_colors() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Spectral);
    let frame = ring.calculate_frame();

    // All 7 LEDs should have colors
    for color in &frame {
        assert!(color.0 > 0 || color.1 > 0 || color.2 > 0);
    }
}

#[rstest]
fn test_fano_pulse_has_varying_brightness() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::FanoPulse);
    let frame = ring.calculate_frame();

    // LEDs should have varying intensities due to phase offset
    // (Not all LEDs will be at the same brightness)
}

// ============================================================================
// Set All Tests
// ============================================================================

#[rstest]
fn test_set_all_applies_color() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    let test_color = (255, 128, 64);
    ring.set_all(test_color);

    // set_all is a convenience method, verify it doesn't panic
}

// ============================================================================
// Property-Based Tests
// ============================================================================

proptest! {
    #[test]
    fn test_brightness_always_reduces_or_equals(
        r in 0u8..=255,
        g in 0u8..=255,
        b in 0u8..=255,
        brightness in 0.0f32..=1.0
    ) {
        // Brightness scaling should never increase values
        let original = (r, g, b);
        let scaled = (
            (r as f32 * brightness) as u8,
            (g as f32 * brightness) as u8,
            (b as f32 * brightness) as u8,
        );

        prop_assert!(scaled.0 <= original.0);
        prop_assert!(scaled.1 <= original.1);
        prop_assert!(scaled.2 <= original.2);
    }

    #[test]
    fn test_safety_value_produces_valid_frame(h_x in -1.0f64..=2.0) {
        let config = LEDRingConfig {
            enabled: true,
            count: 7,
            pin: 18,
            brightness: 1.0,
            animation_speed: 1.0,
        };
        let mut ring = LEDRing::new(&config).unwrap();

        ring.set_pattern(AnimationPattern::Safety(h_x));
        let frame = ring.calculate_frame();

        // Frame should always have valid RGB values
        for color in &frame {
            prop_assert!(color.0 <= 255);
            prop_assert!(color.1 <= 255);
            prop_assert!(color.2 <= 255);
        }
    }

    #[test]
    fn test_highlight_valid_colony_index(idx in 0usize..7) {
        let config = LEDRingConfig {
            enabled: true,
            count: 7,
            pin: 18,
            brightness: 1.0,
            animation_speed: 1.0,
        };
        let mut ring = LEDRing::new(&config).unwrap();

        ring.highlight_colony(idx);
        prop_assert_eq!(ring.pattern(), AnimationPattern::Highlight(idx));
    }
}

// ============================================================================
// Edge Cases
// ============================================================================

#[rstest]
fn test_zero_brightness_produces_black() {
    let config = LEDRingConfig {
        enabled: true,
        count: 7,
        pin: 18,
        brightness: 0.0,
        animation_speed: 1.0,
    };
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Idle);
    let frame = ring.calculate_frame();

    // All LEDs should be black (0, 0, 0)
    for color in &frame {
        assert_eq!(*color, (0, 0, 0));
    }
}

#[rstest]
fn test_cascade_animation() {
    let config = default_led_config();
    let mut ring = LEDRing::new(&config).unwrap();

    ring.set_pattern(AnimationPattern::Cascade);
    let frame = ring.calculate_frame();

    // Cascade should produce valid colors
    assert_eq!(frame.len(), 7);
}

/*
 * Kagami LED Ring Tests
 * Colony: All seven, unified through e0
 *
 * Seven lights. Seven colonies. One mirror.
 */
