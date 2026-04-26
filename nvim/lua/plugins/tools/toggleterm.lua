---@type LazyPluginSpec
return {
  "akinsho/toggleterm.nvim",
  version = "*",
  event = "VeryLazy",
  opts = {
    size = function(term)
      if term.direction == "horizontal" then
        return 20
      elseif term.direction == "vertical" then
        return vim.o.columns * 0.4
      end
    end,
    open_mapping = [[<c-\>]],
    shell = vim.uv.os_uname().sysname == "Windows_NT" and "pwsh" or "zsh",
    winbar = {
      enabled = true,
    },
  },
  keys = function()
    return {
      { "<C-\\>" },
    }
  end,
}
