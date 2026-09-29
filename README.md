# 初始化

- macOS 需要 Command Line Tools、App Store 登录；
- Linux 需要 systemd 用户会话。

私钥副本放到 `~/private-key.asc`（验证后删除）；智能卡运行 `gpg --card-status`。

```sh
bash -c '
set -euo pipefail
config_dir="$HOME/.config"
if [[ ! -e "$config_dir/.git" ]]; then
    checkout="$(mktemp -d)"
    git clone https://github.com/roife/config.git "$checkout"
    mkdir -p "$config_dir"
    cp -a "$checkout/." "$config_dir/"
    rm -rf -- "$checkout"
fi
git -C "$config_dir" remote set-url origin git@github.com:roife/config.git
exec bash "$config_dir/init.sh"
'
```

同名文件覆盖（符号链接须先移除），无关文件保留。已有仓库跳过获取；重跑：`bash ~/.config/init.sh`。
流程：Nix → 激活 → GPG/SSH → Emacs 配置 → 后台重启 → Fish。

Emacs 在后台下载依赖，重跑前保存文件。完成后重新登录。
Home Manager 文件冲突需手动处理。
可选 `GITHUB_TOKEN` 环境变量会自动用于 Nix 构建。
