---@type LazyPluginSpec
return {
  ---@module 'blink.cmp'
  "Saghen/blink.cmp",
  version = "*",
  -- build = "cargo build --release",
  ---@type blink.cmp.Config
  opts = {
    keymap = {
      preset = "super-tab",
    },
    sources = {
      default = {
        "lsp",
        "path",
        "snippets",
        "buffer",
      },
      providers = {
        lsp = {
          name = "LSP",
        },
      },
    },
    completion = {
      list = {
        selection = {
          preselect = function(ctx)
            return ctx.mode ~= "cmdline"
              and not require("blink.cmp").snippet_active { direction = 1 }
          end,
        },
      },
      menu = {
        -- Minimum width should be controlled by components
        min_width = 1,
        draw = {
          columns = {
            { "label", "label_description", gap = 1 },
            { "provider" },
          },
          components = {
            provider = {
              text = function(ctx) return "| " .. ctx.item.source_name:sub(1, 3):upper() end,
            },
          },
        },
      },
      documentation = {
        auto_show = true,
        auto_show_delay_ms = 50,
        update_delay_ms = 50,
      },
    },
    signature = {
      enabled = false,
    },
  },
}
