local function update_colorscheme()
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

  local bg3 = vim.api.nvim_get_hl(0, { name = "GruvboxBg3" })
  vim.api.nvim_set_hl(0, "LspInlayHint", { fg = bg3.fg })
end

---@type LazyPluginSpec
return {
  "sainnhe/gruvbox-material",
  priority = 1000,
  config = function()
    vim.cmd.colorscheme("gruvbox-material")
    update_colorscheme()

    vim.api.nvim_create_autocmd("ColorScheme", {
      callback = function(_) update_colorscheme() end,
    })
  end,
}
