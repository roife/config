{ inputs, pkgs, ... }:
{
  home.packages = [
    inputs.fenix.packages.${pkgs.stdenv.hostPlatform.system}.stable.toolchain
    pkgs.pest-ide-tools
  ];
}
