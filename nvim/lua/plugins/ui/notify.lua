---@type LazyPluginSpec
return {
  "rcarriga/nvim-notify",
  event = "VeryLazy",
  init = function()
    vim.notify = function(...)
      return require('notify')(...)
    end
  end,
  opts = {
    render = "minimal",
    top_down = false,
    stages = "static",
  },
}
