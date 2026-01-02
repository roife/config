---@type LazyPluginSpec
return {
  "rachartier/tiny-glimmer.nvim",
  event = "VeryLazy",
  priority = 10, -- Low priority to catch other plugins' keybindings
  opts = {
    overwrite = {
      yank = {
        default_animation = "custom",
      },
      paste = {
        default_animation = "custom",
      },
      undo = {
        enabled = true,
        default_animation = "custom",
      },
      redo = {
        enabled = true,
        default_animation = "custom",
      },
    },
    animations = {
      custom = {
        max_duration = 200,
        chars_for_max_duration = 15,
        color = "#D7BA7D",
        effect = function (self, _)
          return self.settings.color, 1
        end,
      },
    },
  },
  config = function(_, opts)
    require("tiny-glimmer").setup(opts)
  end,
}

