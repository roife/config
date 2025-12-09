local utils = require("utils")

-- Set diagnostic options
vim.diagnostic.config {
  virtual_text = {
    spacing = 4,
    prefix = "●",
    severity = vim.diagnostic.severity.ERROR,
  },
  float = {
    severity_sort = true,
    source = "if_many",
  },
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = "✘",
      [vim.diagnostic.severity.WARN] = "!",
      [vim.diagnostic.severity.HINT] = "⚑",
      [vim.diagnostic.severity.INFO] = "ℹ",
    },
  },
  severity_sort = true,
}

vim.lsp.inlay_hint.enable()
if vim.lsp.inline_completion then vim.lsp.inline_completion.enable() end

if vim.lsp._folding_range then
  vim.o.foldmethod = "expr"
  vim.o.foldexpr = "v:lua.vim.lsp.foldexpr()"
  vim.o.foldtext = "v:lua.vim.lsp.foldtext()"
  vim.o.foldcolumn = "1"
  vim.o.foldlevel = 99

  vim.api.nvim_create_autocmd("LspNotify", {
    callback = function(args)
      if args.data.method == "textDocument/didOpen" then
        vim.lsp.foldclose("imports", vim.fn.bufwinid(args.buf))
      end
    end,
  })
end

vim.api.nvim_create_autocmd("LspAttach", {
  desc = "General LSP Attach",
  callback = function(args)
    local bufnr = args.buf

    local function nmap_local(lhs, rhs, desc, opts)
      opts = opts or {}
      opts.buffer = bufnr
      if desc then opts.desc = desc end
      vim.keymap.set("n", lhs, rhs, opts)
    end

    vim.keymap.set({ "i", "s" }, "<C-S>", function()
      ---@type vim.lsp.buf.signature_help.Opts
      local config = {}
      vim.lsp.buf.signature_help(vim.tbl_deep_extend("keep", config, {}))
    end, { buffer = bufnr, desc = "References" })

    -- LSP navigation
    nmap_local("gd", vim.lsp.buf.definition, "Definition")
    nmap_local("gD", vim.lsp.buf.type_definition, "Type definition")
    nmap_local("gI", vim.lsp.buf.implementation, "Implementation")

    -- CodeLens
    nmap_local("<leader>lr", vim.lsp.codelens.run, "Run lens")

    -- Call hierarchy
    nmap_local("<leader>li", vim.lsp.buf.incoming_calls, "Incoming calls")
    nmap_local("<leader>lo", vim.lsp.buf.outgoing_calls, "Outgoing calls")

    -- Toggle inlay hints
    function toggle_lsp_inlay_hint()
      vim.lsp.inlay_hint.enable(
        not vim.lsp.inlay_hint.is_enabled { bufnr = bufnr },
        { bufnr = bufnr }
      )
    end
    nmap_local("<leader>lh", toggle_lsp_inlay_hint, "Toggle inlay hints")

    vim.keymap.set("i", "<C-J>", function()
      if not vim.lsp.inline_completion.get() then return "<C-J>" end
    end, {
      expr = true,
      desc = "Accept the current inline completion",
      buffer = bufnr,
    })

    -- Workspace folders
    nmap_local("<leader>lwa", vim.lsp.buf.add_workspace_folder, "Add workspace folder")
    nmap_local("<leader>lwr", vim.lsp.buf.remove_workspace_folder, "Remove workspace folder")
    nmap_local(
      "<leader>lwl",
      function() print(vim.inspect(vim.lsp.buf.list_workspace_folders())) end,
      "List workspace folders"
    )

    -- Use conform instead
    -- vim.keymap.set("n", "<leader>F", function()
    --   vim.lsp.buf.format { async = true }
    -- end, { buffer = bufnr, desc = "Format document" })
  end,
})

vim.lsp.enable {
  "clangd",
  "lua_ls",
  "copilot",
  "pyright",
  "rust-analyzer",
}
