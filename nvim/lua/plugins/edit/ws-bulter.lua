----@type LazyPluginSpec
return {
  "roife/ws-butler.nvim",
  event = "BufReadPost",
  opts = {
    trim_eob = false,
    ignore_filetypes = {},
  },
}
