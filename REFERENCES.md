# 来源、参考与许可说明

本文档说明 Writing Tools 中文增强版与上游项目、参考项目及第三方依赖之间的关系，便于使用者和贡献者准确了解代码来源、设计参考与许可证边界。

## 1. 上游基础：theJayTea/WritingTools

- 上游仓库：<https://github.com/theJayTea/WritingTools>
- 原项目维护者：theJayTea（Jesai Tarun）及上游贡献者
- 上游许可证：GNU General Public License v3.0
- 本仓库关系：GitHub Fork，非官方中文修改版本

本项目继承了上游 WritingTools 的跨应用文本捕获、AI Provider、系统托盘、写作处理和跨平台项目结构，并在此基础上继续开发。中文增强版不是上游项目的官方中文版，上游作者没有为本修改版本的新增功能、配置、二进制发行包或维护行为提供背书。

本仓库保留完整 Git 历史，并继续以 [GNU GPL v3.0](LICENSE) 发布。分发修改后的二进制时，应同时提供对应源代码、保留版权与许可证声明，并注明已经修改。

## 2. Prompt 工作台参考：gaoyechen/SharpInput

- 参考仓库：<https://github.com/gaoyechen/SharpInput>
- 参考版本：SharpInput v3.3
- 参考快照：`0d23ef15682ac2bc05d4954546900ad0a117ee1b`
- 原作者：gaoyechen
- 许可证：MIT License

Prompt 工作台参考并重新实现了 SharpInput 的部分行为契约与工作流理念，主要包括：

- 将“直接回答”与“先优化输入”明确分离；
- 意图识别、场景识别与关键上下文补全；
- 只追问会显著改变结果的问题；
- 按任务风险和复杂度选择不同深度；
- Prompt 编译、质量复审与可复制输出；
- 区分已知事实、假设、约束、成功标准和待补信息。

本项目没有把 SharpInput 作为运行时依赖直接安装，而是针对 PySide6 桌面应用、多 Provider、流式响应、本地偏好、收藏、历史和安全替换等需求进行了独立实现。主要对应文件包括：

- `Windows_and_Linux/sharpinput_workflow.py`
- `Windows_and_Linux/ui/PromptWorkbenchWindow.py`
- `Windows_and_Linux/prompt_presets.py`
- `Windows_and_Linux/prompt_preferences.py`
- `Windows_and_Linux/prompt_library.py`
- `Windows_and_Linux/tests/test_sharpinput_workflow.py`

SharpInput 的 MIT 版权与许可全文已保留在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库作为一个整体继续按照 GPLv3 分发；这不会取消 SharpInput 原作者对其 MIT 许可内容享有的权利。

## 3. 本项目新增设计与实现

以下内容主要由中文增强版在上游基础上新增或重构：

- 中文本地化、中文默认预设及中文输入法状态恢复；
- Windows 原生 `Ctrl+Space` 与 `Ctrl+Shift+P` 全局快捷键；
- 独立 Prompt Provider、Prompt 工作台和场景预设系统；
- Prompt 收藏、版本、长期偏好和本地安全存储；
- 安全替换、差异对比、历史版本与兼容性诊断；
- 统一视觉系统、现代化主面板、设置页、结果页及交互动效；
- 流式输出、长文本渲染优化和可关闭动画；
- 构建、依赖锁定、安全扫描和自动化回归测试。

统一视觉系统与窗口动效为本项目内的代码实现，没有引入或复制第三方 UI 模板。项目使用的图标、Python 包和 Qt 组件仍分别受其原始许可证约束。

## 4. 第三方依赖

直接依赖、版本、许可证和项目地址集中记录在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。依赖包仍受各自许可证约束；本仓库中的列表不替代依赖随附的正式许可证文件。

## 5. 修改记录

- 重要版本与功能变化：[CHANGELOG.md](CHANGELOG.md)
- 非官方修改版本声明：[NOTICE.md](NOTICE.md)
- 本仓库许可证：[LICENSE](LICENSE)
- 上游代码历史：本仓库 Git 提交历史及 `upstream` 远程

如发现来源、作者署名或许可证信息有遗漏，请通过 Issue 或 Pull Request 指出。本说明用于提高来源透明度，不构成法律意见。
