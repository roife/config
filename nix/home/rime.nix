{ config, lib, pkgs, ... }:
let
  rimeDir =
    if pkgs.stdenv.hostPlatform.isDarwin then "${config.home.homeDirectory}/Library/Rime"
    else "${config.xdg.dataHome}/rime";

  schema = "double_pinyin_flypy";
  grammarModel = "wanxiang-lts-zh-hans";

  # Patches in *.custom.yaml, following rime-ice's README and others/patch_examples.
  # Only values that differ from upstream are listed; redeploy Rime after switching.
  patches = {
    default = {
      schema_list = [ { inherit schema; } ];
      "menu/page_size" = 9;
      "switcher/hotkeys" = [ ];
      "ascii_composer/switch_key/Caps_Lock" = "noop";
      "ascii_composer/switch_key/Shift_L" = "noop";
      "key_binder/bindings" = [
        { when = "composing"; accept = "Shift+Tab"; send = "Shift+Left"; }
        { when = "composing"; accept = "Tab"; send = "Shift+Right"; }
        { when = "has_menu"; accept = "minus"; send = "Page_Up"; }
        { when = "has_menu"; accept = "equal"; send = "Page_Down"; }
      ];
    };

    ${schema} = {
      grammar = {
        language = grammarModel;
        non_collocation_penalty = -4;
        collocation_max_length = 5;
        collocation_min_length = 2;
        collocation_penalty = -14;
      };
      "translator/contextual_suggestions" = true;
      "translator/max_homophones" = 6;
      "translator/max_homographs" = 2;
    };

    # Double-pinyin spelling for English derivations and radical lookup.
    melt_eng."speller/algebra".__include = "melt_eng.schema.yaml:/algebra_${schema}";
    radical_pinyin."speller/algebra".__include = "radical_pinyin.schema.yaml:/algebra_${schema}";

    squirrel = {
      app_options = {
        "com.apple.Spotlight".ascii_mode = true;
        "com.mitchellh.ghostty".ascii_mode = true;
        "org.gnu.Emacs" = { ascii_mode = true; no_inline = true; };
      };
      style = {
        color_scheme = "gruvbox_light";
        color_scheme_dark = "gruvbox_dark";
        text_orientation = "horizontal";
        candidate_list_layout = "linear";
        candidate_format = "%c %@";
        inline_preedit = true;
        corner_radius = 6;
        hilited_corner_radius = 0;
        border_height = 0;
        border_width = 0;
        line_spacing = 5;
        spacing = 10;
        font_point = 18;
        label_font_point = 15;
        comment_font_point = 15;
      };
      # Import existing Squirrel presets without copying their color tables.
      "preset_color_schemes/gruvbox_light".__include = "gruvbox_light:/preset_color_schemes/gruvbox_light";
      "preset_color_schemes/gruvbox_dark".__include = "gruvbox_dark:/patch/preset_color_schemes/gruvbox_dark_hard";
    };
  };

  yaml = pkgs.formats.yaml { };
in
{
  # Link files individually so Rime can still write build/, user dbs and sync/.
  home.file = {
    ${rimeDir} = {
      source = "${pkgs.rime-ice}/share/rime-data";
      recursive = true;
    };
    "${rimeDir}/default.yaml".source = "${pkgs.rime-ice}/share/rime-data/rime_ice_suggestion.yaml";
    "${rimeDir}/gruvbox_light.yaml".source = pkgs.fetchurl {
      url = "https://raw.githubusercontent.com/rimeinn/rime-moran/1064ea9aff9a7af64e1912d914d0e9f547557de3/squirrel.yaml";
      hash = "sha256-29bowWGb8fOsn9JGoUbKEPNM9SCCXAgERKEdTe0feC8=";
    };
    "${rimeDir}/gruvbox_dark.yaml".source = pkgs.fetchurl {
      url = "https://raw.githubusercontent.com/z1645444/config/3c36f77da17a88cc340ec1c11ef806a2eefa9259/Rime/squirrel.custom.yaml";
      hash = "sha256-wm2sv++K3/D2no4NYbIkDSj3+0+y9q0FPDkI9i56Sj0=";
    };
    "${rimeDir}/${grammarModel}.gram" = {
      source = pkgs.fetchurl {
        url = "https://github.com/jetcookies/RIME-LMDG-tracker/releases/download/0-unstable-2026-10-09/${grammarModel}.gram";
        hash = "sha256-YWnzXUiqEBjm7/0Wy2rgfzB5ZM/+XYx5uX+vIWRpO+w=";
      };
      force = true; # Replace the file written by the former activation hook.
    };
  } // lib.mapAttrs' (name: patch:
    lib.nameValuePair "${rimeDir}/${name}.custom.yaml" {
      source = yaml.generate "${name}.custom.yaml" { inherit patch; };
    }) patches;

  home.packages = [ pkgs.librime ];
}
