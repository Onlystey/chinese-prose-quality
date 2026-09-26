# 中文写作与逐句校审 / Chinese Prose Quality

面向 Codex 的中文成稿技能：在生成、续写和修订时检查词义、搭配、句法、歧义、逻辑、标点与上下文，覆盖论文、教材、小说及其他中文写作。

主要学习依据为任金璧《现代汉语病句与标点详解》（中国书籍出版社，2020）。本项目将其辨析方法与实际长文修订需求结合，使用原创规则表达和原创评测例句；不是原书电子版或题库。详细依据见[来源说明](skills/chinese-prose-quality/references/source-notes.md)。

## 使用方式

安装后可直接提出中文写作、续写或校订任务，也可以显式调用：

```text
请使用 $chinese-prose-quality 校订这篇文字。保留原意和文体，
修正全文同类问题，并复核修改后的指代、逻辑与标点。
```

常规输出为干净成稿；只有需要审计或仍有待核实项时，才附修订说明。

## 安装

需要 Python 3.9 或更新版本，不需要第三方 Python 包。仓库下载或克隆后，在根目录运行：

```bash
python3 tools/install.py install
python3 tools/install.py status
```

安装器将技能实体保存到 `~/.codex/skills/chinese-prose-quality`（或指定的 `CODEX_HOME` 下），在 `~/.agents/skills` 建立兼容链接，并将一段有起止标记的触发与验收指令加入全局 `AGENTS.md`。已有无关内容保留；同名未受管目录或冲突链接不会被覆盖。请先查看安装器帮助了解自定义 home 与 Codex home 的参数。

```bash
python3 tools/install.py --help
python3 tools/install.py uninstall
```

卸载只处理本技能受管文件、兼容链接和标记内指令；对手工修改过的安装文件拒绝悄悄删除。备份不会替换用户后续新增的全局指令。

若有非空全局 `AGENTS.override.md`，它可能遮蔽 `AGENTS.md`，需根据当前有效指令链处理；安装器不擅自更改 override。项目级要求仍需遵守。

## 全局生效范围

“全局”指使用该本机 Codex home 和技能目录的 Codex 环境，不自动覆盖云端任务、其他主机、独立配置目录或一般 ChatGPT 对话。技能通常可自动发现；若看不到，重开会话或重启应用。旧聊天是否刷新取决于宿主版本，不能仅凭文件落盘保证。

官方说明：[技能发现与安装位置](https://learn.chatgpt.com/docs/build-skills)、[AGENTS.md加载方式](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。全局指令负责主动触发，详细规则按文体载入。

## 文件组织

- `skills/chinese-prose-quality/SKILL.md`：入口、执行流程和验收条件。
- `references/`：病句、标点数字、审校方法、学术/教材/小说规则、长文回归与反误报。
- `scripts/text_audit.py`：只读候选定位器，报告少数表面风险；不自动改稿。
- `evals/`：原创正反与语境评测，含行为评分要求。
- `tools/install.py`：可重复安装、状态与受控卸载。
- `tests/`：安装器和候选定位器的行为检查。

## 验证与边界

```bash
python3 -m unittest discover -s tests -v
```

另需按 `evals/README.md` 对真实模型输出作语义评估。静态校验只证明技能文件结构有效；脚本通过只证明脚本在测试条件下符合预期；少数写作样例通过也不能保证所有未来文字没有病句。

本技能不靠禁词表判断，不把省略、倒装、合理修辞或人物口语一律判错。不虚构引用和数据，不承诺 AIGC 检测分数。个人偏好可以保存在本地 `CODEX_HOME/writing-profiles/chinese-prose-quality.md`，无需把私人稿件放入公开仓库。

## 开源与贡献

本仓库原创内容采用 MIT 许可。书籍、标准和其他第三方来源的权利不因本许可改变。仓库不包含扫描书、全文OCR、私人聊天、未发表稿件或真实批注。提交新规则时，提供适用条件、反例、原创测试与可核实依据，避免把个人偏好包装成普遍语法定律。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 本次交付的测试记录

[171项行为评测与差异裁定](evals/adjudication-2026-09-26.md)保留了原始结果，区分标签一致、语义接受与需收紧的风格边界。测试结果不能被转述成“171项全部证明零病句”。

## 发布到 GitHub

本目录可作为独立仓库根目录：新建公开仓库后上传本目录内的文件，保留 `skills/`、`tools/`、`tests/` 和 `evals/` 的结构。发布前确认没有加入个人偏好、私有阅读记录、原书或真实稿件。GitHub仓库的创建和公开发布是单独动作；准备好本目录不代表已经发布。
