---@type LazyPluginSpec
return {
  "pwntester/octo.nvim",
  cmd = { "Octo" },
  init = function()
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "octo",
      desc = "Name Octo tabs",
      callback = function() require("utils").set_tabname("octo") end,
    })
  end,
  opts = {
    picker = "fzf-lua",
    picker_config = {
      use_emojis = true,
    },
  },
}
