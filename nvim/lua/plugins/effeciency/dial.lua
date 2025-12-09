---@type LazyPluginSpec
return {
  "monaqa/dial.nvim",
  keys = {
    {
      "<C-c>",
      function() require("dial.map").manipulate("increment", "normal") end,
    },
    {
      "<C-x>",
      function() require("dial.map").manipulate("decrement", "normal") end,
    },
    {
      "g<C-c>",
      function() require("dial.map").manipulate("increment", "gnormal") end,
    },
    {
      "g<C-x>",
      function() require("dial.map").manipulate("decrement", "gnormal") end,
    },
    {
      "<C-c>",
      function() require("dial.map").manipulate("increment", "visual") end,
      mode = "v",
    },
    {
      "<C-x>",
      function() require("dial.map").manipulate("decrement", "visual") end,
      mode = "v",
    },
    {
      "g<C-c>",
      function() require("dial.map").manipulate("increment", "gvisual") end,
      mode = "v",
    },
    {
      "g<C-x>",
      function() require("dial.map").manipulate("decrement", "gvisual") end,
      mode = "v",
    },
  },
}
