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
vim.lsp.inline_completion.enable()
vim.lsp.document_color.enable()
vim.lsp.semantic_tokens.enable()

vim.api.nvim_create_autocmd("LspNotify", {
  callback = function(args)
    if args.data.method == "textDocument/didOpen" then
      vim.lsp.foldclose("imports", vim.fn.bufwinid(args.buf))
    end
  end,
})

vim.api.nvim_create_autocmd("LspAttach", {
  desc = "General LSP Attach",
  callback = function(args)
    local bufnr = args.buf
    local client = assert(vim.lsp.get_client_by_id(args.data.client_id))

    local function nmap_local(lhs, rhs, desc, opts)
      opts = opts or {}
      opts.buffer = bufnr
      if desc then opts.desc = desc end
      vim.keymap.set("n", lhs, rhs, opts)
    end

    vim.keymap.set(
      { "i", "s" },
      "<C-S>",
      function() vim.lsp.buf.signature_help(vim.tbl_deep_extend("keep", {}, {})) end,
      { buffer = bufnr, desc = "References" }
    )

    -- LSP navigation
    nmap_local("gd", vim.lsp.buf.definition, "Definition")
    nmap_local("gD", vim.lsp.buf.declaration, "Declaration")
    nmap_local("gt", vim.lsp.buf.type_definition, "Type definition")
    nmap_local("gI", vim.lsp.buf.implementation, "Implementation")
    nmap_local("gr", vim.lsp.buf.references, "Implementation")

    -- CodeLens
    nmap_local("<leader>llr", vim.lsp.codelens.run, "Run lens")

    -- Call hierarchy
    nmap_local("<leader>lci", vim.lsp.buf.incoming_calls, "Incoming calls")
    nmap_local("<leader>lco", vim.lsp.buf.outgoing_calls, "Outgoing calls")

    -- Toggle inlay hints
    local function toggle_lsp_inlay_hint()
      vim.lsp.inlay_hint.enable(
        not vim.lsp.inlay_hint.is_enabled { bufnr = bufnr },
        { bufnr = bufnr }
      )
    end
    nmap_local("<leader>lih", toggle_lsp_inlay_hint, "Toggle inlay hints")

    nmap_local("<leader>lca", vim.lsp.buf.code_action, "Code Action")

    -- Workspace folders
    nmap_local("<leader>lwa", vim.lsp.buf.add_workspace_folder, "Add workspace folder")
    nmap_local("<leader>lwr", vim.lsp.buf.remove_workspace_folder, "Remove workspace folder")
    nmap_local(
      "<leader>lwl",
      function() print(vim.inspect(vim.lsp.buf.list_workspace_folders())) end,
      "List workspace folders"
    )

    -- Folding
    if client:supports_method('textDocument/foldingRange', bufnr) then
      vim.o.foldexpr = 'v:lua.vim.lsp.foldexpr()'
      vim.o.foldtext = 'v:lua.vim.lsp.foldtext()'
    end
  end,
})

-- LSP document highlight groups
vim.api.nvim_set_hl(0, "LspReferenceText",  { underline = true })
vim.api.nvim_set_hl(0, "LspReferenceRead",  { underline = true })
vim.api.nvim_set_hl(0, "LspReferenceWrite", { underline = true })

vim.lsp.enable {
  "clangd",
  "emmylua_ls",
  "copilot",
  --"rust-analyzer",
  "tinymist",
  "pyrefly",
}
