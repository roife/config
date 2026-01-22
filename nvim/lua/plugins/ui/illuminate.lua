---@type LazyPluginSpec
return {
  "RRethy/vim-illuminate",
  cond = vim.lsp.document_highlight == nil,
  event = "VeryLazy",
  opts = function()
    return {
      filetypes_denylist = {
        "xxd",
        "floggraph",
      },
      large_file_cutoff = 10000,
      should_enable = function(bufnr)
        local win = vim.fn.bufwinid(bufnr)
        -- Very bad performance in diff-mode
        if vim.api.nvim_win_is_valid(win) and vim.wo[win].diff then return false end
        return true
      end,
    }
  end,
  config = function(_, opts)
    local illuminate = require("illuminate")
    illuminate.configure(opts)

    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordText",
      { underline = true, bold = true }
    )
    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordRead",
      { underline = true, bold = true }
    )

    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordWrite",
      { underline = true, bold = true })

  end,
  keys = {
    {
      "]r",
      function() require("illuminate").goto_next_reference() end,
      desc = "Next reference",
    },
    {
      "[r",
      function() require("illuminate").goto_prev_reference() end,
      desc = "Prev reference",
    },
    {
      "<leader>ti",
      function() require("illuminate").toggle_freeze_buf() end,
      desc = "Toggle Freeze reference",
    },
  },
}
