---@type LazyPluginSpec
return {
  "Mr-LLLLL/interestingwords.nvim",
  event = "VeryLazy",
  opts = {
    colors = {
      "#c27c82",
      "#aac6a6",
      "#66b3c5",
      "#d19546",
      "#d1b500",
      "#929fd2",
      "#ba95c4",
    },
    color_key = "<leader>ii", -- 按键来标记单词的触发键
    cancel_color_key = "<leader>ic",
    scroll_center = false,
  },

  config = function(_, opts)
    local iw = require("interestingwords")
    iw.setup(opts)
    vim.keymap.del("n", "<leader>M")
  end,
}
