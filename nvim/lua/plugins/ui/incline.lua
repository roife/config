local utils = require("utils")

---@type LazyPluginSpec
return {
  "b0o/incline.nvim",
  event = "VeryLazy",
  opts = {
    window = {
      margin = {
        horizontal = 0,
      },
    },
    hide = {
      only_win = true,
    },
    render = function(props)
      local path = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(props.buf), ":.")
      if path == "" then path = "[No Name]" end
      path = utils.shorten_path(path, "/", 25)
      local modified = vim.bo[props.buf].modified
      return {
        { path, gui = modified and "bold,italic" or "bold" },
      }
    end,
  },
  config = function(_, opts) require("incline").setup(opts) end,
}
