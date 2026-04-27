--- @type LazyPluginSpec
return {
  "nvim-focus/focus.nvim",
  version = false,
  lazy = false,
  opts = {
    autoresize = {
      enable = true,
      minwidth = 20,
      minheight = 5,
    },
    ui = {
      cursorline = false,
      signcolumn = false,
    },
  },
  config = function(_, opts)
    local focus = require("focus")
    focus.setup(opts)

    focus.focus_disable()

    vim.keymap.set("n", "<leader>tf", "<cmd>FocusToggle<CR>", {
      desc = "Toggle Focus resize",
    })
  end,
}
