# 刚认识不久 Just met · 刚认识小屋 英语自习室

由 **cici · Eddie** 主理（小屋管家 **Darcy** 陪伴）的 **「刚认识小屋」** 英语精听跟读 Web 应用，整合了「小屋大厅」「英语自习室」「生词本」「进阶权益与积分中心」以及隔壁《重生之我上恋综了》（`https://justmet.pages.dev`）入口。

## 核心功能
- **沉浸式精听跟读工作台**：
  - 4 种学习模式：`⇄ 双语 / EN / ZH` 三态切换、`跟读`（单句聚焦 + 录音回放 + AI 逐词音素级评测）、`挖空`（斜纹遮罩点击揭示）、`听写词`（填对自动跳格 + 自动播下一句 + 手机端防键盘遮挡）。
  - 17 项播放控制：小窗、全屏、画内/画下字幕、AB 片段复读、0.5x–2.0x 倍速、盲听模糊遮罩、单句循环 & 纯音频模式、整句 IPA 音标、连播/句停（连播自动跳过 >2.5s 纯 BGM 空档）、屏词、字号调节、12 套护眼主题、PDF 双语讲义导出。
  - **实时真词典查词（`/api/define`）**：点击任意单词/短语调用 Gemini 返回精准词性、美/英 IPA、中英文释义、地道双语例句及本集原句语境，并本地持久化缓存。
- **双轨音画同步 & 零占用本地空间**：
  - 视频/音频素材存放于外接硬盘并通过软链接挂载到 `content/episodes/`；
  - `scripts/dev_server.py` 支持 HTTP `206 Range` 分段流式播放与实时词典接口。
- **自动化字幕精校与独立质检门禁**：
  - `scripts/sync_episodes.py`：智能归组音画/封面/字幕、按真实句末标点拆合、裁剪超长 BGM 拖尾、自动识别博主/难度/8 大标签；
  - `scripts/ai_polish_subtitles.py`：支持 Gemini API 断点续传精校（补标点 + 地道中文 + IPA + 重点词）；
  - `scripts/qa_gate.py`：硬性红线门禁（0 缺中文、0 纯标点中文、0 超长 BGM 拖尾、0 时间轴重叠、品牌文案检查）。

## 本地运行方式
```bash
# 1. 启动支持 HTTP Range + 实时词典的本地服务（可选传入 GEMINI_API_KEY 开启实时真词典）
GEMINI_API_KEY="你的Key" python3 scripts/dev_server.py 4174

# 2. 浏览器访问
# http://127.0.0.1:4174/

# 3. 同步外接硬盘新素材并运行质检门禁
python3 scripts/sync_episodes.py
python3 scripts/qa_gate.py
```

## 目录结构
- `index.html` / `styles.css`：前端主入口与 12 套主题样式
- `js/app.js` / `js/views.js` / `js/practice.js` / `js/speech.js` / `js/store.js` / `js/data.js`：前端核心逻辑
- `js/local_episodes.js`：由 `sync_episodes.py` 自动生成的 39 期精校剧集元数据与双语字幕
- `scripts/dev_server.py` / `scripts/sync_episodes.py` / `scripts/ai_polish_subtitles.py` / `scripts/qa_gate.py`：本地服务、同步、精校与质检脚本
- `AGENTS.md`：双 Agent 独立质检协作红线

> 说明：大体积视频/音频文件（`.mp4` / `.m4a`）已通过 `.gitignore` 排除，不上传至 GitHub；未来上线部署建议使用 Cloudflare Pages（前端）+ Cloudflare R2（音视频）。
