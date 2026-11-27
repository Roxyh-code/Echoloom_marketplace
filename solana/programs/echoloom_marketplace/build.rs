use std::{env, fs, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-env-changed=ECHOOLOOM_BOOTSTRAP_AUTHORITY");
    let value = env::var("ECHOOLOOM_BOOTSTRAP_AUTHORITY").unwrap_or_else(|_| {
        panic!("ECHOOLOOM_BOOTSTRAP_AUTHORITY is required; no insecure fallback is allowed")
    });
    let decoded = bs58::decode(&value)
        .into_vec()
        .unwrap_or_else(|_| panic!("ECHOOLOOM_BOOTSTRAP_AUTHORITY must be a base58 public key"));
    if decoded.len() != 32 {
        panic!("ECHOOLOOM_BOOTSTRAP_AUTHORITY must decode to exactly 32 bytes");
    }
    if decoded.iter().all(|byte| *byte == 0) {
        panic!("ECHOOLOOM_BOOTSTRAP_AUTHORITY cannot be the default public key");
    }
    let bytes = decoded
        .iter()
        .map(u8::to_string)
        .collect::<Vec<_>>()
        .join(", ");
    let output = format!("pub const BOOTSTRAP_AUTHORITY_BYTES: [u8; 32] = [{bytes}];\n");
    let destination = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR is set"))
        .join("bootstrap_authority.rs");
    fs::write(destination, output).expect("write generated bootstrap key");
}
