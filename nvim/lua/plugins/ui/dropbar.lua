---@type LazyPluginSpec
return {
  "Bekaboo/dropbar.nvim",
  event = "VeryLazy",
  opts = {
    icons = {
      kinds = {
        dir_icon = "",
        file_icon = "",
        symbols = "",
      },
      ui = {
        bar = { separator = " ❯ ", extends = "…" },
        menu = { separator = " ", indicator = "❯" },
      },
    },
    bar = {
      padding = { left = 0, right = 0 },
      enable = false,
      sources = function(buf, _)
        local sources = require("dropbar.sources")
        local utils = require("dropbar.utils")

        vim.api.nvim_set_hl(0, 'DropBarFileName', { bold = true })
        local custom_path = {
          get_symbols = function(buff, win, cursor)
            local symbols = sources.path.get_symbols(buff, win, cursor)
            symbols[#symbols].name_hl = 'DropBarFileName'
            return symbols
          end,
        }

        if vim.bo[buf].ft == "markdown" then
          return {
            sources.path,
            sources.markdown,
          }
        end
        if vim.bo[buf].buftype == "terminal" then return {
          sources.terminal,
        } end
        return {
          custom_path,
          utils.source.fallback {
            sources.lsp,
            sources.treesitter,
          },
        }
      end,
      update_debounce = 150,
    },
  },
}
