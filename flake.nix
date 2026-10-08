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
        username =
          let env = builtins.getEnv "HOME_MANAGER_USERNAME";
          in if env == "" then "roifewu" else env;
        name = "roife";
        fullName = "roifewu";
        email = "roifewu@gmail.com";
      };

      inherit (nixpkgs) lib;
      systems = [ "aarch64-darwin" "x86_64-linux" ];

      # Shared Home Manager configuration plus the platform layer ./nix/home/<system>.nix.
      mkHome = system: graphical: home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs = { inherit inputs user graphical; };
        modules = [ ./nix/home ./nix/home/${system}.nix ];
      };
    in {
      homeConfigurations = {
        "${user.username}@aarch64-darwin" = mkHome "aarch64-darwin" true;
        "${user.username}@x86_64-linux" = mkHome "x86_64-linux" true;
        "${user.username}@x86_64-linux-headless" = mkHome "x86_64-linux" false;
      };

      formatter = lib.genAttrs systems (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);
    };
}
