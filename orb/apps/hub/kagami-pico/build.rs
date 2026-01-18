//! Build script for Kagami Pico
//!
//! Sets up the linker script for RP2040

fn main() {
    // Tell cargo to pass the linker script to the linker
    println!("cargo:rustc-link-arg-bins=--nmagic");
    println!("cargo:rustc-link-arg-bins=-Tlink.x");
    println!("cargo:rustc-link-arg-bins=-Tdefmt.x");
}
