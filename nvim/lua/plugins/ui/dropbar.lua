---@type LazyPluginSpec
local utils = require("utils")

local custom_path = {
  get_symbols = function(buff, win, cursor)
    local symbols = require("dropbar.sources").path.get_symbols(buff, win, cursor)
    vim.api.nvim_set_hl(0, "DropBarFileName", { italic = true })
    symbols[#symbols].name_hl = "DropBarFileName"
    if vim.bo[buff].modified then symbols[#symbols].name = symbols[#symbols].name .. " *" end
    return symbols
  end,
}

---@type LazyPluginSpec
return {
  "Bekaboo/dropbar.nvim",
  event = {
    "BufRead",
    "BufNewFile",
  },
  opts = {
    icons = {
      kinds = {
        dir_icon = utils.empty_str(),
        file_icon = utils.empty_str(),
        symbols = utils.empty_str(),
      },
      ui = {
        bar = { separator = " ❯ ", extends = "…" },
      },
    },
    bar = {
      sources = function(buf, _)
        local sources = require("dropbar.sources")
        local utils = require("dropbar.utils")
        if vim.bo[buf].ft == "markdown" then
          return {
            custom_path,
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
    },
  },
}
