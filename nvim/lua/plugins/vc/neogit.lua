---@type LazyPluginSpec
return {
  "NeogitOrg/neogit",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "sindrets/diffview.nvim",
  },
  cmd = {
    "Neogit",
  },
  keys = {
    { "<leader>gg", "<Cmd>Neogit<CR>", desc = "Open Neogit" },
  },
  opts = {
    disable_hint = true,
    graph_style = "unicode",
    remember_settings = true,
    integrations = {
      fzf_lua = true,
      diffview = true,
    },
    sections = {
      stashes = {
        folded = false,
      },
      recent = {
        folded = false,
      },
    },
    status = {
      recent_commit_count = 20,
    },
  },
}
