---@LazyPlugSpec
return {
  "Vigemus/iron.nvim",
  config = function()
    local view = require("iron.view")
    require("iron.core").setup {
      config = {
        repl_open_cmd = view.split.vertical.botright("40%"),
      },
    }
  end,
}
