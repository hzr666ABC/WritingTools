# Writing Tools 中文增强版

> 基于 [theJayTea/WritingTools](https://github.com/theJayTea/WritingTools) 的非官方中文社区版本。
> 本项目不是原项目的官方中文版，也不代表原作者发布或背书。

[![安全检查](https://github.com/hzr666ABC/WritingTools/actions/workflows/security.yml/badge.svg)](https://github.com/hzr666ABC/WritingTools/actions/workflows/security.yml)
[![许可证：GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
[![最新版本](https://img.shields.io/github/v/release/hzr666ABC/WritingTools?display_name=tag&sort=semver)](https://github.com/hzr666ABC/WritingTools/releases/latest)

Writing Tools 中文增强版是一款 Windows 全局 AI 写作助手。选中文本并按下快捷键，即可改写、校对、总结、翻译或执行自己的提示词；也可以连接 Gemini、OpenAI 兼容服务、Groq 和本地 Ollama。

这个分支在保留原项目核心能力的基础上，重点改进中文体验、交互效率、外观和本地数据安全。

## 与原版相比增加了什么

- 完整中文界面与中文默认预设。
- 现代化设置页、快捷弹窗和应用图标。
- 可自定义窗口背景、字体比例和预设图标。
- 按键录入式快捷键设置，无需手工输入组合键。
- 记住上一次操作，可在按下主快捷键后直接执行。
- 弹窗数字键快速选择预设，选择后自动关闭。
- 单实例运行，重复启动不会产生多个独立实例。
- 自定义提示词与内置基础提示词组合，提升预设输出稳定性。
- 安全应用：应用前差异对比、撤销、恢复原文。
- Provider Studio：服务地址、模型、连通性与兼容性诊断。
- 本地安全密钥库：Windows 使用 DPAPI；Linux/macOS 后备实现使用 AES-256-GCM。
- 加密历史与版本恢复、预设导入导出和分享。
- 依赖哈希锁定、Git 历史密钥扫描、静态安全分析与 SBOM。

## 下载与安装

1. 打开 [Releases](https://github.com/hzr666ABC/WritingTools/releases/latest)。
2. 下载 `Writing.Tools.Windows.Custom.Release.zip`。
3. 解压到一个固定且可写的目录。
4. 运行 `Writing Tools CN.exe`。

这是便携版应用。不要直接在 ZIP 压缩包内运行，也不要把程序放入需要管理员权限才能写入的目录。

当前增强版主要面向 Windows 10/11。仓库仍保留上游 Linux 与 macOS 源码，但本项目发布的二进制仅针对 Windows。

## 快速使用

1. 从系统托盘打开设置。
2. 选择 Gemini、OpenAI 兼容服务或 Ollama。
3. 填写 API Key、服务地址和模型，然后运行兼容性测试。
4. 在任意应用中选中文本。
5. 按下主快捷键，选择预设；也可以启用“记住上次操作”直接执行。

快捷弹窗支持方向键、Enter、Esc 和数字键快速选择。API Key 只应填写在应用的安全密钥库中，不要写入代码、Issue、日志或预设导出文件。

## 隐私与安全

- API Key 在 Windows 上通过当前用户的 DPAPI 加密保存。
- 历史正文加密保存在本地；部分用于列表展示的时间、类型等元数据可能保持明文。
- 使用云端 Provider 时，用户选中的文本和提示词会发送给对应服务商处理。
- 使用本地 Ollama 时，可将推理数据保留在本机。
- 诊断报告默认对密钥、URL 凭据、用户目录和敏感路径进行脱敏。
- 项目不附带任何开发者或用户的 API Key。

本地加密主要降低配置文件意外泄露风险，不能防御已经以同一系统用户权限运行的恶意程序。发现安全问题时，请按照 [SECURITY.md](SECURITY.md) 私下报告，不要先创建公开 Issue。

## 从源代码运行

需要 Python 3.11 或兼容版本。Windows PowerShell 示例：

```powershell
cd Windows_and_Linux
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-lock.txt
.\.venv\Scripts\python.exe main.py
```

详细说明：

- [从源代码运行](README's%20Linked%20Content/To%20Run%20Writing%20Tools%20Directly%20from%20the%20Source%20Code.md)
- [构建 Windows 程序](README's%20Linked%20Content/To%20Compile%20the%20Application%20Yourself.md)

## 开发与同步上游

建议所有修改都在独立分支完成：

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/your-feature
```

同步原项目更新时，先在临时分支解决冲突和完成测试：

```powershell
git fetch upstream
git switch -c sync/upstream-next main
git merge upstream/main
```

通用修复会尽量拆分为独立 Pull Request 贡献给原项目；中文界面和具有明确产品定位的定制功能由本分支持续维护。

## 发布完整性

每个正式版本应同时提供：

- Windows ZIP 发布包；
- CycloneDX SBOM；
- SHA-256 校验清单；
- 与二进制完全对应的 Git 标签和源代码。

发布前安全检查可在仓库根目录运行：

```powershell
python scripts/security_check.py --history
```

## 项目来源与许可证

本项目修改自 [theJayTea/WritingTools](https://github.com/theJayTea/WritingTools)，感谢 Jesai、Arya Mirsepasi 以及所有上游贡献者。

本项目继续按照 [GNU General Public License v3.0](LICENSE) 发布。分发修改后的二进制时，必须同时向用户提供对应源代码，并保留原项目的版权、许可证和修改说明。第三方组件信息见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，版本变更见 [CHANGELOG.md](CHANGELOG.md)。
