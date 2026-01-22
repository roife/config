---@type LazyPluginSpec
return {
  "sainnhe/gruvbox-material",
  priority = 1000,
  config = function()
    vim.g.gruvbox_material_enable_bold = true
    vim.g.gruvbox_material_enable_italic = true
    vim.g.gruvbox_material_better_performance = 1
    vim.g.gruvbox_material_dim_inactive_windows = 1

    vim.cmd.colorscheme("gruvbox-material")
  end,
}
