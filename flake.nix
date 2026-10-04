{
  description = "roife's Home Manager configuration for macOS and Linux";

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
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";
    fenix = {
      url = "github:nix-community/fenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ nixpkgs, home-manager, ... }:
    let
      user = {
        name = "roife";
        fullName = "roifewu";
        email = "roifewu@gmail.com";
      };

      # Shared Home Manager configuration plus one platform layer.
      mkHome = system: layer: home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs = { inherit inputs user; };
        modules = [ ./nix/home layer ];
      };
    in {
      homeConfigurations = {
        "${user.fullName}@aarch64-darwin" = mkHome "aarch64-darwin" ./nix/home/darwin.nix;
        "${user.fullName}@x86_64-linux" = mkHome "x86_64-linux" ./nix/home/linux.nix;
      };

      formatter = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ]
        (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);
    };
}
