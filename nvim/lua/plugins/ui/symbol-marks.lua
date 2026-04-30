---@type LazyPluginSpec
return {
  dir = "~/code/symbol-marks.nvim/",
  opts = {
    colors = {
      "#8C9A8F", -- 灰绿（sage）
      "#A58F86", -- 灰玫瑰棕
      "#7E8DA6", -- 灰蓝
      "#B0A28C", -- 灰卡其
      "#9C7F8F", -- 灰紫
      "#6F8F8B", -- 蓝绿色（teal-muted）
      "#B7AFA3", -- 浅灰米色
      "#8D6E63", -- 灰棕（偏暖）
    },
  },
  keys = {
    {
      "<leader>wi",
      function() require("symbol_marks").toggle() end,
      desc = "Toggle Symbol Overlay",
      mode = { "n", "v" },
    },
    {
      "<leader>wr",
      function() require("symbol_marks").rename() end,
      desc = "Replace Symbol",
    },
    {
      "<leader>wc",
      function() require("symbol_marks").clear() end,
      desc = "Delete All Symbols",
    },
  },
  lazy = false,
  setup = function(_, opts) require("symbol_marks").setup(opts) end,
}
