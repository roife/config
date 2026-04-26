---@type LazyPluginSpec
return {
  "rbong/vim-flog",
  init = function()
    vim.g.flog_enable_extended_chars = 1
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "floggraph",
      desc = "Name Flog tabs",
      callback = function() require("utils").set_tabname("flog") end,
    })
  end,
  dependencies = {
    "tpope/vim-fugitive",
  },
  cmd = "Flog",
}
