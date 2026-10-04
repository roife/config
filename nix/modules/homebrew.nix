# Home Manager counterpart of nix-darwin's `homebrew.{brews,casks,masApps}`.
#
# Homebrew itself is installed and pinned by nix-homebrew. It only ships a
# nix-darwin module, so it is evaluated on its own (with freeform stand-ins for
# the nix-darwin options it sets) to reuse its setup script, `brew` launcher
# and fish integration. Packages are then applied with `brew bundle`.
{ config, inputs, lib, pkgs, ... }:
let
  inherit (lib) mkOption types;
  cfg = config.homebrew;

  nixHomebrew = (lib.evalModules {
    specialArgs = { inherit pkgs; };
    modules = [
      inputs.nix-homebrew.darwinModules.nix-homebrew
      {
        freeformType = types.lazyAttrsOf types.anything;
        homebrew.enable = false;
        nix-homebrew = {
          enable = true;
          autoMigrate = true;
          user = config.home.username;
        };
      }
    ];
  }).config;

  setupHomebrew = pkgs.writeShellScript "setup-homebrew"
    nixHomebrew.system.activationScripts.setup-homebrew.text;

  brewfile = pkgs.writeText "Brewfile" (lib.concatLines (
    map (name: ''brew "${name}", trusted: true'') cfg.brews
    ++ map (name: ''cask "${name}", trusted: true'') cfg.casks
    ++ lib.mapAttrsToList (name: id: ''mas "${name}", id: ${toString id}'') cfg.masApps
  ));
in
{
  options.homebrew = {
    brews = mkOption { type = types.listOf types.str; default = [ ]; };
    casks = mkOption { type = types.listOf types.str; default = [ ]; };
    masApps = mkOption { type = types.attrsOf types.ints.positive; default = { }; };
  };

  config = {
    home.packages = nixHomebrew.environment.systemPackages;
    programs.fish.interactiveShellInit = nixHomebrew.programs.fish.interactiveShellInit;

    # Runs as root like under nix-darwin; init.sh keeps the sudo timestamp fresh.
    # Skipped when neither the setup script nor the Brewfile changed since the last run.
    home.activation.homebrew = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      (
        stamp="${config.xdg.stateHome}/home-manager/homebrew-stamp"
        want="${setupHomebrew} ${brewfile}"
        if [[ -x /opt/homebrew/bin/brew && -f "$stamp" && "$(< "$stamp")" == "$want" ]]; then
          verboseEcho "Homebrew is up to date, skipping"
          exit 0
        fi

        # Home Manager resets PATH; Bundle finds mas in the caller's PATH.
        export PATH="$PATH:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
        export HOMEBREW_NO_AUTO_UPDATE=1
        run /usr/bin/sudo ${setupHomebrew}
        run /opt/homebrew/bin/brew bundle install --no-upgrade --file=${brewfile}

        if [[ ! -v DRY_RUN ]]; then
          mkdir -p "''${stamp%/*}"
          printf '%s' "$want" > "$stamp"
        fi
      )
    '';
  };
}
