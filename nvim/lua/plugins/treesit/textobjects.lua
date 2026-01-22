---@type LazyPluginSpec
return {
  "nvim-treesitter/nvim-treesitter-textobjects",
  branch = "main",
  dependencies = {
    { "ghostbuster91/nvim-next" },
  },
  init = function() vim.g.textobjects_enable_mappings = 0 end,
  opts = {
    select = {
      lookahead = true,
      include_surrounding_whitespace = true,
    },
    move = {
      set_jumps = true,
    },
  },
  keys = function()
    local ts = vim._defer_require("nvim-treesitter-textobjects", {
      repeatable_move = {}, ---@module "nvim-treesitter-textobjects.repeatable_move"
      select = {}, ---@module "nvim-treesitter-textobjects.select"
      move = {}, ---@module "nvim-treesitter-textobjects.move"
    })

    return {
      ---
      --- Repeatable
      ---
      {
        ";",
        function() ts.repeatable_move.repeat_last_move() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Next last move",
      },
      {
        ",",
        function() ts.repeatable_move.repeat_last_move_opposite() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Prev last move",
      },
      {
        "f",
        function() return ts.repeatable_move.builtin_f_expr() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Move to next char",
      },
      {
        "F",
        function() return ts.repeatable_move.builtin_F_expr() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Move to prev char",
      },
      {
        "t",
        function() return ts.repeatable_move.builtin_t_expr() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Move before next char",
      },
      {
        "T",
        function() return ts.repeatable_move.builtin_T_expr() end,
        expr = true,
        mode = { "n", "x", "o" },
        desc = "Move before prev char",
      },
      --
      -- Select
      --
      {
        "aa",
        function() ts.select.select_textobject("@parameter.outer") end,
        mode = { "x", "o" },
        desc = "a argument",
      },
      {
        "ia",
        function() ts.select.select_textobject("@parameter.inner") end,
        mode = { "x", "o" },
        desc = "inner part of a argument",
      },
      {
        "af",
        function() ts.select.select_textobject("@function.outer") end,
        mode = { "x", "o" },
        desc = "a function region",
      },
      {
        "if",
        function() ts.select.select_textobject("@function.inner") end,
        mode = { "x", "o" },
        desc = "inner part of a function region",
      },
      {
        "ac",
        function() ts.select.select_textobject("@class.outer") end,
        mode = { "x", "o" },
        desc = "a of a class",
      },
      {
        "ic",
        function() ts.select.select_textobject("@class.inner") end,
        mode = { "x", "o" },
        desc = "inner part of a class region",
      },
      {
        "ab",
        function() ts.select.select_textobject("@block.outer") end,
        mode = { "x", "o" },
        desc = "a block",
      },
      {
        "ib",
        function() ts.select.select_textobject("@block.inner") end,
        mode = { "x", "o" },
        desc = "inner part of a block",
      },
      {
        "an",
        function() ts.select.select_textobject("@number.outer") end,
        mode = { "x", "o" },
        desc = "a loop",
      },
      {
        "in",
        function() ts.select.select_textobject("@number.inner") end,
        mode = { "x", "o" },
        desc = "inner part of a number",
      },
      --
      -- Move
      --
      {
        "]a",
        function() ts.move.goto_next_start("@parameter.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next argument start",
      },
      {
        "]A",
        function() ts.move.goto_next_end("@parameter.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next argument end",
      },
      {
        "[a",
        function() ts.move.goto_previous_start("@parameter.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous argument start",
      },
      {
        "[A",
        function() ts.move.goto_previous_end("@parameter.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous argument end",
      },
      {
        "]f",
        function() ts.move.goto_next_start("@function.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next function start",
      },
      {
        "]F",
        function() ts.move.goto_next_end("@function.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next function end",
      },
      {
        "[f",
        function() ts.move.goto_previous_start("@function.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous function start",
      },
      {
        "[F",
        function() ts.move.goto_previous_end("@function.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous function end",
      },
      {
        "]c",
        function() ts.move.goto_next_start("@class.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next class start",
      },
      {
        "]C",
        function() ts.move.goto_next_end("@class.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next class end",
      },
      {
        "[c",
        function() ts.move.goto_previous_start("@class.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous class start",
      },
      {
        "[C",
        function() ts.move.goto_previous_end("@class.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous class end",
      },
      {
        "]b",
        function() ts.move.goto_next_start("@block.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next block start",
      },
      {
        "]B",
        function() ts.move.goto_next_end("@block.outer") end,
        mode = { "n", "x", "o" },
        desc = "Next block end",
      },
      {
        "[b",
        function() ts.move.goto_previous_start("@block.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous block start",
      },
      {
        "[B",
        function() ts.move.goto_previous_end("@block.outer") end,
        mode = { "n", "x", "o" },
        desc = "Previous block end",
      },
      {
        "[n",
        function() ts.move.goto_previous_start("@number.inner") end,
        mode = { "n", "x", "o" },
        desc = "Previous number",
      },
      {
        "]n",
        function() ts.move.goto_next_start("@number.inner") end,
        mode = { "n", "x", "o" },
        desc = "Next number",
      },
      {
        "[N",
        function() ts.move.goto_previous_end("@number.inner") end,
        mode = { "n", "x", "o" },
        desc = "Previous number",
      },
      {
        "]N",
        function() ts.move.goto_next_end("@number.inner") end,
        mode = { "n", "x", "o" },
        desc = "Next number",
      },
    }
  end,
}
