---@type LazyPluginSpec
return {
  "max397574/better-escape.nvim",
  opts = {
    default_mappings = false,
    mappings = {
      i = {
        i = {
          i = "<Esc>",
        },
      },
      c = {
        i = {
          i = "<C-c>",
        },
      },
      t = {
        i = {
          i = "<C-\\><C-n>",
        },
      },
      s = {
        i = {
          i = "<Esc>",
        },
      },
    },
    timeout = vim.o.timeoutlen,
  },
}
