---@type LazyPluginSpec
return {
  "windwp/nvim-autopairs",
  event = "InsertEnter",
  opts = {},
  config = function(_, opts)
    local npairs = require("nvim-autopairs")
    local Rule = require("nvim-autopairs.rule")

    npairs.setup(opts)

    -- Automatically insert balanced spaces
    npairs.add_rules {
      Rule(" ", " ")
        :with_pair(function(opts)
          local pair = opts.line:sub(opts.col - 1, opts.col)
          return pair == "()" or pair == "[] " or pair == "{}"
        end)
        :with_move(function(opts) return opts.prev_char:match(".%s") ~= nil end)
        :use_key(" "),
    }
  end,
}
