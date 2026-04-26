---@type LazyPluginSpec
return {
  "NeogitOrg/neogit",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "esmuellert/codediff.nvim",
  },
  cmd = {
    "Neogit",
  },
  init = function()
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "Neogit*",
      desc = "Name Neogit tabs",
      callback = function() require("utils").set_tabname("neogit") end,
    })
  end,
  keys = {
    { "<leader>gg", "<Cmd>Neogit<CR>", desc = "Open Neogit" },
  },
  opts = {
    disable_hint = true,
    graph_style = "unicode",
    remember_settings = true,
    integrations = {
      fzf_lua = true,
      codediff = true,
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
