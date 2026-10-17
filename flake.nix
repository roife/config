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
    colorscheme.url = "github:roife/nix-colorscheme";
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

      # Shared Home Manager configuration plus the platform layer ./nix/home/<system>.nix.
      # Add new homes here; outputs below are derived from this set.
      homes = {
        aarch64-darwin = { system = "aarch64-darwin"; };
        x86_64-linux = { system = "x86_64-linux"; };
        x86_64-linux-headless = { system = "x86_64-linux"; graphical = false; };
      };

      mkHome = { system, graphical ? true }: home-manager.lib.homeManagerConfiguration {
        pkgs = nixpkgs.legacyPackages.${system};
        extraSpecialArgs = { inherit inputs user graphical; };
        modules = [ ./nix/home ./nix/home/${system}.nix ];
      };

      configs = lib.mapAttrs (_: mkHome) homes;
      systems = lib.unique (lib.catAttrs "system" (lib.attrValues homes));
    in {
      homeConfigurations =
        lib.mapAttrs' (name: lib.nameValuePair "${user.username}@${name}") configs;

      checks = lib.genAttrs systems (system:
        lib.mapAttrs (name: _: configs.${name}.activationPackage)
          (lib.filterAttrs (_: home: home.system == system) homes));

      formatter = lib.genAttrs systems (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);
    };
}
