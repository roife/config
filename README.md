# 新系统初始化

macOS 上请先登录 Mac App Store（`Brewfile` 会通过 `mas` 安装应用，包括 Xcode）。

Linux 上脚本会放置 Rime 方案，但不会安装 Fcitx5 输入法本身；需要使用 Rime 时，请另行安装 Fcitx5 及其 Rime 组件。

## 1. 运行初始化脚本

```sh
bash ./init.sh
```

在仓库根目录手动运行 Nix 命令时，使用 `nix/` 作为 flake 路径，例如 `nix develop path:./nix#rust-nightly`。

## 2. 恢复 GPG 私钥

安装好 GPG 后，从可信备份导入私钥并确认能列出它：

```sh
gpg --import /path/to/private-key.asc
gpg --list-secret-keys A63DE4903F5E1486A4FBB656E09D9EE312C4C223
bash "$HOME/.config/init.sh" --configure-gpg-ssh
```

最后一条命令只配置 GPG SSH，不会重新执行其他初始化步骤。

如果密钥保存在智能卡上，先用 `gpg --card-status` 让 GPG 识别它。Linux 上若没有 `gpg` 命令，需先通过系统包管理器安装 GnuPG。不要将明文私钥放入本仓库。
