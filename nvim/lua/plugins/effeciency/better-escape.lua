---@type LazyPluginSpec
return {
  "max397574/better-escape.nvim",
  opts = {
    default_mappings = false,
    mapping = {
      i = {
        j = {
          j = "<Esc>",
        },
      },
      c = {
        j = {
          j = "<C-c>",
        },
      },
      t = {
        j = {
          j = "<C-\\><C-n>",
        },
      },
      s = {
        j = {
          j = "<Esc>",
        },
      },
    },
    timeout = vim.o.timeoutlen,
  },
}
