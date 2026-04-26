---@type LazyPluginSpec
return {
  "esmuellert/codediff.nvim",
  cmd = "CodeDiff",
  init = function()
    vim.api.nvim_create_autocmd("User", {
      pattern = "CodeDiffOpen",
      desc = "Name CodeDiff tabs",
      callback = function() require("utils").set_tabname("codediff") end,
    })
  end,
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
  },
}
