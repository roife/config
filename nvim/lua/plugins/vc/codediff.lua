---@type LazyPluginSpec
return {
  "esmuellert/codediff.nvim",
  cmd = "CodeDiff",
  opts = {
    diff = {
      ignore_trim_whitespace = true,
      compute_moves = true,
    },

    explorer = {
      icons = {
        folder_closed = "-",
        folder_open = "+",
      },
      view_mode = "tree",
    },
  },
  keys = {
    { "<leader>gdo", "<Cmd>CodeDiff<CR>", desc = "Open" },
    { "<leader>gdh", "<Cmd>CodeDiff history<CR>", desc = "Open History" },
    {
      "<leader>gdf",
      "<Cmd>CodeDiff file HEAD<CR>",
      desc = "Current History",
    },
  }
}
