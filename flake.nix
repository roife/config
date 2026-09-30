{
  description = "Command-line tools managed by Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    plasma-manager = {
      url = "github:nix-community/plasma-manager";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.home-manager.follows = "home-manager";
    };
    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";
    fenix = {
      url = "github:nix-community/fenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    flake-utils.url = "github:numtide/flake-utils";
    rime.url = "path:./nix/rime";
  };

  outputs = { nixpkgs, home-manager, plasma-manager, nix-darwin, nix-homebrew, fenix, flake-utils, rime, ... }:
    let
      homeModules = [ ./nix/home.nix rime.homeManagerModules.default ];
    in {
      darwinConfigurations.roifewu = nix-darwin.lib.darwinSystem {
        modules = [
          nix-homebrew.darwinModules.nix-homebrew
          home-manager.darwinModules.home-manager
          ./nix/darwin.nix
          {
            home-manager = {
              useGlobalPkgs = true;
              backupFileExtension = "backup";
              extraSpecialArgs.fenixPackages = fenix.packages.aarch64-darwin;
              users.roifewu.imports = homeModules;
            };
          }
        ];
      };

      homeConfigurations."roifewu@x86_64-linux" = home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.x86_64-linux;
        extraSpecialArgs.fenixPackages = fenix.packages.x86_64-linux;
        modules = homeModules ++ [
          plasma-manager.homeModules.plasma-manager
          ./nix/kde.nix
        ];
      };
    };
}
