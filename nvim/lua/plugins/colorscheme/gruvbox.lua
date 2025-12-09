---@type LazyPluginSpec
return {
  "ellisonleao/gruvbox.nvim",
  priority = 1000,
  opts = {},
  config = function(_, opts)
    require("gruvbox").setup(opts)
    vim.cmd.colorscheme("gruvbox")
    vim.api.nvim_set_hl(0, "SignColumn", { bg = "NONE" })

    local yellow_bold = vim.api.nvim_get_hl(0, { name = "GruvboxYellowBold" })
    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordText",
      { underline = true, bold = true, fg = yellow_bold.fg }
    )
    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordRead",
      { underline = true, bold = true, fg = yellow_bold.fg }
    )
    local orange_bold = vim.api.nvim_get_hl(0, { name = "GruvboxOrangeBold" })
    vim.api.nvim_set_hl(
      0,
      "IlluminatedWordWrite",
      { underline = true, bold = true, fg = orange_bold.fg }
    )
  end,
}
