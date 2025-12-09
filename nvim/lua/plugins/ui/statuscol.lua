---@type LazyPluginSpec
return {
  "luukvbaal/statuscol.nvim",
  opts = function()
    local builtin = require("statuscol.builtin")

    return {
      bt_ignore = { "nofile", "terminal" },
      ft_ignore = { "NeogitStatus" },
      segments = {
        -- Simulate the sign column while not showing the gitsigns
        {
          sign = {
            name = { ".*" },
            text = { ".*" },
          },
          click = "v:lua.ScSa",
        },
        -- Show gitsigns at the position of line numbers' right padding
        {
          sign = {
            namespace = { "gitsigns" },
            colwidth = 1,
            wrap = true,
            foldclosed = true,
          },
          condition = {
            function(args) return vim.b[args.buf].gitsigns_status end,
          },
          click = "v:lua.ScSa",
        },
      },
    }
  end,
}
