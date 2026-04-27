local utils = require("utils")

local function get_hl_bg(name)
  local hl = vim.api.nvim_get_hl(0, { name = name, link = false })
  while hl.link do
    hl = vim.api.nvim_get_hl(0, { name = hl.link, link = false })
  end
  return hl.bg
end

local function set_hl()
  local add_bg = get_hl_bg("DiffAdd")
  local del_bg = get_hl_bg("DiffDelete")

  if add_bg then
    vim.api.nvim_set_hl(0, "DiffsAddText", {
      bg = utils.adjust_brightness(add_bg, -20),
    })
  end

  if del_bg then
    vim.api.nvim_set_hl(0, "DiffsDeleteText", {
      bg = utils.adjust_brightness(del_bg, -20),
    })
  end
end

---@type LazyPluginSpec
return {
  "barrettruth/diffs.nvim",
  lazy = false,
  init = function()
    vim.g.diffs = {
      hide_prefix = true,
      integrations = {
        neogit = true,
        gitsigns = true,
      },
    }

    vim.api.nvim_create_autocmd("ColorScheme", {
      desc = "Set diffs highlights",
      callback = set_hl,
    })
  end,
  config = function() set_hl() end,
}
