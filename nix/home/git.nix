{ user, ... }:
{
  # Use GitHub's SSH endpoint on port 443 for networks that block port 22.
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    settings."github.com" = {
      HostName = "ssh.github.com";
      Port = 443;
      User = "git";
      HostKeyAlias = "github.com";
    };
  };

  programs.git = {
    enable = true;
    lfs.enable = true;
    settings = {
      user = {
        name = user.name;
        inherit (user) email;
      };
      core = {
        quotepath = false;
        untrackedCache = true;
      };
      init.defaultBranch = "main";
      fetch.prune = true;
      push.autoSetupRemote = true;
      rerere.enabled = true;
      merge.conflictStyle = "zdiff3";
      diff.algorithm = "histogram";
      github.user = user.name;
    };
    ignores = [
      # macOS and Windows
      ".DS_Store"
      ".AppleDouble"
      ".LSOverride"
      ".Spotlight-V100/"
      ".Trashes/"
      "Icon?"
      "._*"
      "Thumbs.db*"
      "ehthumbs.db"
      "ehthumbs_vista.db"
      "Desktop.ini"
      "$RECYCLE.BIN/"

      # Editor backups and per-user state; shared project settings stay visible.
      "*~"
      ".nfs*"
      "**/.idea/workspace.xml"
      "**/.idea/tasks.xml"
      "**/.idea/shelf/"
      "**/.idea/httpRequests/"
      "**/.idea/dataSources.local.xml"
      "xcuserdata/"
      "*.xcuserstate"
      "*.sublime-workspace"
      "*.sw?"
      "Session.vim"
      "\\#*#"
      ".#*"
      "*.orig"
      "*.rej"

      # C/C++ intermediate files and build-system caches.
      "*.o"
      "*.obj"
      "*.lo"
      "*.gch"
      "*.pch"
      "*.ilk"
      "*.idb"
      "*.ipch"
      "CMakeFiles/"
      "CMakeCache.txt"
      "cmake_install.cmake"
      "cmake-build-*/"
      "autom4te.cache/"
      ".deps/"
      ".libs/"
      ".ninja_deps"
      ".ninja_log"

      # Java/JVM: compiled classes, Gradle state, and crash dumps.
      "*.class"
      ".gradle/"
      "hs_err_pid*"
      "replay_pid*"

      # Python bytecode, environments, test caches, and package metadata.
      "__pycache__/"
      "*.py[cod]"
      "*.egg-info/"
      ".eggs/"
      ".pytest_cache/"
      ".mypy_cache/"
      ".ruff_cache/"
      ".hypothesis/"
      ".tox/"
      ".nox/"
      ".venv/"
      "venv/"
      ".coverage"
      ".coverage.*"
      "htmlcov/"

      # Rust/Cargo and SwiftPM build output; keep their lockfiles.
      "target/"
      "*.rs.bk"
      ".build/"

      # Web dependencies, framework output, bundler caches, and tool logs.
      "node_modules/"
      ".pnpm-store/"
      ".next/"
      ".nuxt/"
      ".svelte-kit/"
      ".angular/"
      ".astro/"
      ".parcel-cache/"
      ".turbo/"
      ".vite/"
      ".eslintcache"
      ".stylelintcache"
      ".sass-cache/"
      ".nyc_output/"
      "npm-debug.log*"
      "yarn-debug.log*"
      "yarn-error.log*"
      "pnpm-debug.log*"

      # Other toolchains and local tool state.
      ".vs/"
      "*.csproj.user"
      "*.sln.docstates"
      ".dart_tool/"
      ".pub-cache/"
      ".zig-cache/"
      "zig-out/"
      ".bundle/"
      ".direnv/"

      # Local overrides; environment templates and shared settings stay visible.
      ".env.local"
      ".env.*.local"
      "**/.claude/settings.local.json"
    ];
  };

  programs.difftastic = {
    enable = true;
    git.enable = true;
  };

  programs.gh = {
    enable = true;
    gitCredentialHelper.enable = false;
    settings = {
      prefer_editor_prompt = "enabled";
      aliases.co = "pr checkout";
      color_labels = "enabled";
      spinner = "disabled";
    };
  };
}
