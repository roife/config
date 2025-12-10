---@type LazyPluginSpec
return {
  "gbprod/yanky.nvim",
  event = "VeryLazy",
  keys = {
    -- Put
    { "p", "<Plug>(YankyPutAfter)", mode = { "n", "x" } },
    { "P", "<Plug>(YankyPutBefore)", mode = { "n", "x" } },
    { "gp", "<Plug>(YankyGPutAfter)", mode = { "n", "x" } },
    { "gP", "<Plug>(YankyGPutBefore)", mode = { "n", "x" } },

    -- Cycle history
    { "<C-p>", "<Plug>(YankyPreviousEntry)", mode = "n" },
    { "<C-n>", "<Plug>(YankyNextEntry)", mode = "n" },
  },
  opts = {
    highlight = {
      timer = 200,
    },
  },
}
