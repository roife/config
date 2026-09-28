# 新系统初始化

macOS:
- 登录 Mac App Store（`Brewfile` 会通过 `mas` 安装应用）
- 配置 Xcode command line tools

Linux:
- 提前安装 GnuPG、pinentry、Git 和 SSH 客户端
- 会放置 Rime 方案，但不会安装 Fcitx5 输入法本身

首次运行前，将私钥备份临时放到 `~/private-key.asc`，并确认对应 SSH 公钥已添加到 GitHub。
脚本会导入密钥，确认指定私钥存在后删除这个临时文件；导入或检查失败时保留文件。
如果密钥保存在智能卡上，先用 `gpg --card-status` 让 GPG 识别它，无需放置私钥文件。
请保留另一份安全备份，不要把唯一备份放在这里。

```sh
bash ./init.sh
```

中途失败后，修复报错原因，再运行同一条命令即可；已有安装和仓库会复用，配置会重新应用。

在仓库根目录手动运行 Nix 命令时，使用 `nix/` 作为 flake 路径，例如 `nix develop path:./nix#rust-nightly`。
