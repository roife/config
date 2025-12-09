---@type LazyPluginSpec
return {
  "goolord/alpha-nvim",
  opts = function()
    local startify = require("alpha.themes.startify")
    startify.file_icons.enabled = false
    startify.section.header.val = ""
    return startify.config
  end,
}
