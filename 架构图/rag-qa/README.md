# 《三国演义》知识智能问答 — 设计文档

本目录保存对话中输出的**设计框架**原文，便于查阅与对照实现代码。

## 文档索引

| 文件 | 内容 |
|------|------|
| [01-架构设计.md](./01-架构设计.md) | 多路检索（混合 / 图谱链接 / 目录）、CoT 路由、Rerank、生成、Web 总体架构 |
| [02-持久化与LangChain.md](./02-持久化与LangChain.md) | 库表模型、LangChain/LangGraph 映射、分步 LLM/工具清单、前端契约 |
| [03-LLM调用规范.md](./03-LLM调用规范.md) | 对齐 `1-情感分析-Qwen.py` 的 DashScope 调用、各步骤模型选型 |
| [04-实现对照.md](./04-实现对照.md) | 设计项与当前仓库代码、路径、启动方式的对应关系 |

## 阅读顺序建议

1. **01** — 理解业务与三路检索分工  
2. **03** — 确认 API Key 与模型  
3. **02** — 持久化与 LangChain（生产扩展参考）  
4. **04** — 对照已落地的 MVP 代码  

## 相关代码目录

```
rag/          # 灌库、检索、路由、流水线
api/main.py   # FastAPI
web/          # 对话页面
data/         # rag.db、embeddings.npz（运行 ingest 后生成）
```

## 快速启动（实现）

Mac 已在 `~/.zshrc` 配置 `DASHSCOPE_API_KEY` 时，**无需虚拟环境**：

```bash
cd /Users/zhuchunguang/Desktop/three_kingdoms
chmod +x start.sh ingest.sh   # 首次
./ingest.sh                   # 首次或更新 wiki 后灌库
./start.sh                    # 启动 Web
```

浏览器打开 http://127.0.0.1:8000/
