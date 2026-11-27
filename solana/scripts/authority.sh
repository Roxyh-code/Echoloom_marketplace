cd .. &&
export ECHOOLOOM_BOOTSTRAP_AUTHORITY="$(solana-keygen pubkey .local/bootstrap-authority.json)" &&
cargo test &&
cargo clippy --all-targets -- -D warnings &&
cargo fmt --all -- --check

echo "exit=$?"