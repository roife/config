-- @type: LazyPluginSpec
return {
  'chomosuke/typst-preview.nvim',
  ft = 'typst',
  opts = {
    invert_colors = 'auto',
    dependencies_bin = {
      ['tinymist'] = "tinymist",
    },
  },
}
