---@type LazyPluginSpec
return {
  "jghauser/fold-cycle.nvim",
  event = "VeryLazy",
  config = function()
    require("fold-cycle").setup()
    vim.keymap.set(
      "n",
      "<leader>z",
      function() return require("fold-cycle").open() end,
      { silent = true, desc = "Fold-cycle: open folds" }
    )
    vim.keymap.set(
      "n",
      "<leader>Z",
      function() return require("fold-cycle").open_all() end,
      { silent = true, desc = "Fold-cycle: open all folds" }
    )
  end,
}
