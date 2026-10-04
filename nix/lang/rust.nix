{ inputs, pkgs, ... }:
{
  home.packages = [
    (inputs.fenix.packages.${pkgs.stdenv.hostPlatform.system}.stable.withComponents [
      "cargo"
      "rustc"
      "clippy"
      "rustfmt"
      "rust-src"
      "rust-analyzer"
    ])
    pkgs.pest-ide-tools
  ];
}
