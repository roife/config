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
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, home-manager, fenix, flake-utils, ... }:
    let
      systems = [ "aarch64-darwin" "x86_64-linux" ];
      mkHome = system: home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs.fenixPackages = fenix.packages.${system};
        modules = [ ./home.nix ];
      };
    in {
      homeConfigurations = builtins.listToAttrs (map (system: {
        name = "roifewu@${system}";
        value = mkHome system;
      }) systems);
    } // flake-utils.lib.eachSystem systems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        jdk = pkgs.temurin-bin-21;
      in {
        devShells = {
          rust-nightly = pkgs.mkShell {
            packages = [ fenix.packages.${system}.minimal.toolchain ];
          };
          java21 = pkgs.mkShell {
            packages = [ jdk ];
            JAVA_HOME = jdk.home;
          };
        };
      });
}
