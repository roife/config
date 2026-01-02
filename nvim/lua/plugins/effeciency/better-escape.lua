---@type LazyPluginSpec
return {
  "max397574/better-escape.nvim",
  opts = {
    mapping = { "jj" },
    timeout = vim.o.timeoutlen,
  },
  config = function()
    require("better_escape").setup()
  end,
}
