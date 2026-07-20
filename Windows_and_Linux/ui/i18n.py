"""Simplified Chinese translations for the customized Windows build."""

from __future__ import annotations


ZH_CN = {
    "About Writing Tools": "关于写作工具",
    "Writing Tools is a free & lightweight tool that helps you improve your writing with AI, similar to Apple's new Apple Intelligence feature. It works with an extensive range of AI LLMs, both online and locally run.": "写作工具是一款免费、轻量的 AI 写作助手，可连接在线或本地运行的多种大语言模型。",
    "Created with care by Jesai, a high school student.": "由高中生 Jesai 用心创作。",
    "Feel free to check out my other AI app": "也欢迎体验作者的另一款 AI 应用",
    "It's a novel AI tutor that's free on the Google Play Store :)": "这是一款可在 Google Play 免费使用的 AI 学习助手。",
    "Contact me": "联系作者",
    "Writing Tools would not be where it is today without its <u>amazing</u> contributors": "感谢所有为写作工具作出贡献的<u>优秀贡献者</u>",
    "Extensively refactored Writing Tools and added OpenAI Compatible API support, streamed responses, and the text generation mode when no text is selected.": "重构了大量代码，并加入 OpenAI 兼容接口、流式响应和文本生成模式。",
    "Added Linux support, switched to the pynput API to improve Windows stability. Added Ollama API support, custom options and localization. Fixed misc. bugs and added graceful termination support by handling SIGINT signal.": "加入 Linux、Ollama、自定义预设和本地化支持，并提升 Windows 稳定性。",
    "Added Linux support, switched to the pynput API to improve Windows stability. Added Ollama API support, core logic for customizable buttons, and localization. Fixed misc. bugs and added graceful termination support by handling SIGINT signal.": "加入 Linux、Ollama、自定义预设和本地化支持，并提升 Windows 稳定性。",
    "Helped add dark mode, the plain theme, tray menu fixes, and UI improvements.": "协助实现深色模式、纯色主题、托盘菜单修复和界面改进。",
    "Helped improve the reliability of text selection.": "提升了文本选择的可靠性。",
    "Made the rounded corners anti-aliased & prettier.": "改进了圆角抗锯齿效果。",
    "Significantly improved the About window, making it scrollable and cleaning things up. Also improved our .gitignore & requirements.txt.": "改进了关于页面、忽略规则和依赖清单。",
    "Helped add the start-on-boot setting.": "协助加入开机启动设置。",
    "Describe your change...": "描述你想要的修改…",
    "Ask your AI...": "向 AI 提问…",
    "Proofread": "校对",
    "Rewrite": "改写",
    "Friendly": "更友好",
    "Professional": "更专业",
    "Concise": "更简洁",
    "Summary": "总结",
    "Key Points": "关键要点",
    "Table": "表格",
    "Welcome to Writing Tools": "欢迎使用写作工具",
    "Instantly optimize your writing with AI by selecting your text and invoking Writing Tools with \"ctrl+space\", anywhere.": "在任意应用中选中文字并按下 Ctrl+Space，即可用 AI 优化内容。",
    "Get a summary you can chat with of articles, YouTube videos, or documents by select all text with \"ctrl+a\"": "使用 Ctrl+A 选择文章、视频字幕或文档，即可生成可继续追问的总结。",
    "(or select the YouTube transcript from its description), invoking Writing Tools, and choosing Summary.": "选择内容后打开写作工具并使用“总结”即可。",
    "Chat with AI anytime by invoking Writing Tools without selecting any text.": "无需选择文字也可以随时打开写作工具与 AI 对话。",
    "Supports an extensive range of AI models:": "支持多种 AI 模型：",
    "Gemini 2.0": "Gemini 系列",
    "ANY OpenAI Compatible API — including local LLMs!": "任意 OpenAI 兼容接口，包括本地模型。",
    "Choose your theme:": "选择界面主题：",
    "Gradient": "柔光",
    "Plain": "纯色",
    "Next": "下一步",
    "Response": "处理结果",
    "Select to copy with formatting": "选择内容并保留格式复制",
    "Copy as Markdown": "复制为 Markdown",
    "Thinking": "正在处理",
    "Ask a follow-up question": "继续追问",
    "Settings": "设置",
    "Start on Boot": "开机启动",
    "Shortcut Key:": "主快捷键：",
    "Background Theme:": "背景主题：",
    "Blurry Gradient": "柔光渐变",
    "Choose AI Provider:": "选择 AI 服务：",
    "Finish AI Setup": "完成 AI 设置",
    "Save": "保存",
    "Please restart Writing Tools for changes to take effect.": "设置保存后会立即生效。",
    "About": "关于",
    "Pause": "暂停",
    "Resume": "继续运行",
    "Exit": "退出",
    "Error": "错误",
}


def translate(message: str) -> str:
    """Translate a source message, falling back without raising."""

    return ZH_CN.get(message, message)
