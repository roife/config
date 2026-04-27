---@type LazyPluginSpec
return {
  "luukvbaal/statuscol.nvim",
  opts = {
    ft_ignore = { "NeogitStatus" },
    segments = {
      { text = { " " } },
      {
        sign = { namespace = { "diagnostic%.signs" }, maxwidth = 1, colwidth = 1 },
        click = "v:lua.ScSa",
      },
      {
        sign = {
          name = { ".*" },
          text = { ".*" },
          maxwidth = 3,
          colwidth = 1,
          auto = true,
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
  },
}
