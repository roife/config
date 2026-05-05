---@type LazyPluginSpec
return {
  "nvim-java/nvim-java",
  opts = {
    jdk = {
      auto_install = false,
    },
  },
  config = function(_, opts)
    require("java").setup(opts)

    local home = vim.env.JDTLS_JAVA_HOME
    if home ~= "" then
      vim.lsp.config("jdtls", {
        cmd_env = {
          JAVA_HOME = home,
          PATH = table.concat({ home .. "/bin", vim.env.PATH or "" }, ":"),
        },
      })
    end

    vim.lsp.enable("jdtls")
  end,
}
