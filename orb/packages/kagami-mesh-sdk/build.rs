//! Build script for kagami-mesh-sdk
//!
//! The UniFFI proc macros handle binding generation automatically.
//! This build script is minimal since we use the proc macro approach.

fn main() {
    // UniFFI proc macros handle everything automatically
    // No UDL file needed with the modern approach

    // Rerun if Cargo.toml changes
    println!("cargo:rerun-if-changed=Cargo.toml");
}
