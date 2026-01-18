//! UniFFI binding generator binary.
//!
//! Generates Swift and Kotlin bindings from the kagami-mesh-sdk library.

use camino::Utf8PathBuf;
use std::env;
use uniffi_bindgen::BindgenCrateConfigSupplier;

/// Empty config supplier - we don't use external configs
struct EmptyConfigSupplier;

impl BindgenCrateConfigSupplier for EmptyConfigSupplier {
    fn get_toml(&self, _crate_name: &str) -> anyhow::Result<Option<toml::value::Table>> {
        Ok(None)
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();

    // Default paths
    let lib_path = if cfg!(target_os = "macos") {
        "target/release/libkagami_mesh_sdk.dylib"
    } else {
        "target/release/libkagami_mesh_sdk.so"
    };

    // Parse simple command line: uniffi-bindgen [swift|kotlin|all]
    let target = args.get(1).map(|s| s.as_str()).unwrap_or("all");

    let lib = camino::Utf8Path::new(lib_path);

    match target {
        "swift" => generate_swift(lib),
        "kotlin" => generate_kotlin(lib),
        "all" | _ => {
            generate_swift(lib);
            generate_kotlin(lib);
        }
    }
}

fn generate_swift(lib: &camino::Utf8Path) {
    println!("Generating Swift bindings...");
    let out_dir = Utf8PathBuf::from("bindings/swift");
    std::fs::create_dir_all(&out_dir).expect("Failed to create swift output directory");

    uniffi_bindgen::library_mode::generate_bindings(
        lib,
        None,
        &uniffi_bindgen::bindings::SwiftBindingGenerator,
        &EmptyConfigSupplier,
        None,
        &out_dir,
        false,
    ).expect("Failed to generate Swift bindings");

    println!("✓ Swift bindings written to bindings/swift/");
}

fn generate_kotlin(lib: &camino::Utf8Path) {
    println!("Generating Kotlin bindings...");
    let out_dir = Utf8PathBuf::from("bindings/kotlin");
    std::fs::create_dir_all(&out_dir).expect("Failed to create kotlin output directory");

    uniffi_bindgen::library_mode::generate_bindings(
        lib,
        None,
        &uniffi_bindgen::bindings::KotlinBindingGenerator,
        &EmptyConfigSupplier,
        None,
        &out_dir,
        false,
    ).expect("Failed to generate Kotlin bindings");

    println!("✓ Kotlin bindings written to bindings/kotlin/");
}
