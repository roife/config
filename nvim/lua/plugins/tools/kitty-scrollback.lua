---@type LazyPluginSpec
return {
  "mikesmithgh/kitty-scrollback.nvim",
  cmd = {
    "KittyScrollbackGenerateKittens",
    "KittyScrollbackCheckHealth",
  },
  event = { "User KittyScrollbackLaunch" },
  opts = {
    {
      callbacks = {
        after_paste_window_ready = function(pastewin_data)
          local winid = pastewin_data.paste_window.winid
          vim.wo[winid].statuscolumn = ""
        end,
      },
    },
  },
}
