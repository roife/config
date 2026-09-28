{
  description = "Rime scheme and grammar for Home Manager";

  inputs = {
    rime-frost = {
      url = "github:gaboolic/rime-frost";
      flake = false;
    };
    rime-grammar = {
      url = "file+https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram";
      flake = false;
    };
  };

  outputs = { rime-frost, rime-grammar, ... }: {
    homeManagerModules.default = import ./module.nix {
      rimeFrost = rime-frost;
      rimeGrammar = rime-grammar;
    };
  };
}
