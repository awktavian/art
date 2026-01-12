//! Kagami Orb Base Station Firmware
//!
//! Controls the magnetic levitation and wireless power transfer systems
//! for the Kagami Orb floating display.
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────┐
//! │                    Base Station                          │
//! │                                                          │
//! │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
//! │  │  Levitation  │  │     WPT      │  │     LED      │   │
//! │  │  Controller  │  │  Controller  │  │   Animator   │   │
//! │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
//! │         │                 │                 │           │
//! │  ┌──────┴─────────────────┴─────────────────┴───────┐   │
//! │  │              State Coordinator                    │   │
//! │  └──────────────────────┬───────────────────────────┘   │
//! │                         │                               │
//! │  ┌──────────────────────┴───────────────────────────┐   │
//! │  │                    HAL                            │   │
//! │  │   DAC  │  ADC  │  I2C  │  SPI  │  GPIO           │   │
//! │  └───────────────────────────────────────────────────┘   │
//! └─────────────────────────────────────────────────────────┘
//! ```

#![no_std]
#![no_main]
#![feature(type_alias_impl_trait)]

pub mod levitation;
pub mod error;

// Re-exports
pub use levitation::{
    HeightController,
    LevitationMode,
    HeightTrajectory,
    BobbleAnimation,
    LevitationState,
    LevitationSafetyVerifier,
};
pub use error::{BaseError, BaseResult};
