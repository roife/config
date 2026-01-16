---@type LazyPluginSpec
return {
  "max397574/better-escape.nvim",
  opts = {
    default_mappings = false,
    mappings = {
      i = {
        j = {
          k = "<Esc>",
        },
      },
      c = {
        j = {
          k = "<C-c>",
        },
      },
      t = {
        j = {
          j = {
            j = "<C-\\><C-n>",
          },
        },
      },
      s = {
        j = {
          k = "<Esc>",
        },
      },
    },
    timeout = vim.o.timeoutlen,
  },
}
