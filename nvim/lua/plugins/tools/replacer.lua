-- ---@type LazyPluginSpec
return {
  "gabrielpoca/replacer.nvim",
  opts = { rename_files = false },
  keys = {
    {
      "<leader>h",
      function() require("replacer").run() end,
      desc = "run replacer.nvim",
    },
  },
}
