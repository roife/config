{
  description = "Command-line tools managed by Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    fenix = {
      url = "github:nix-community/fenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, home-manager, fenix, ... }:
    let
      pkgsFor = system: import nixpkgs { inherit system; };
      mkHome = system: home-manager.lib.homeManagerConfiguration {
        pkgs = pkgsFor system;
        extraSpecialArgs = { inherit fenix system; };
        modules = [ ./home.nix ];
      };
    in {
      homeConfigurations = {
        "roifewu@aarch64-darwin" = mkHome "aarch64-darwin";
        "roifewu@x86_64-linux" = mkHome "x86_64-linux";
      };

      devShells = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ] (system:
        let pkgs = pkgsFor system;
        in {
          rust-nightly = pkgs.mkShell {
            packages = [ fenix.packages.${system}.minimal.toolchain ];
          };
          java21 = pkgs.mkShell {
            packages = [ pkgs.temurin-bin-21 ];
            JAVA_HOME = pkgs.temurin-bin-21.home;
          };
        });
    };
}
