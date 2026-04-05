# ZZZ-Agent TODO

## 战略方向

Claude 做大脑（看画面 → 决策 → 调度），一条龙做手脚（执行自动化模块）。
不重复造轮子 —— 截图/OCR/输入/导航/节点执行这些框架已经有了，薄薄地包一层就行。

核心闭环：
```
get_screenshot / get_screen_state  →  Claude 判断
      ↓
list_available_apps / get_daily_summary  →  Claude 挑模块
      ↓
start_app(app_id)  →  一条龙执行
      ↓
get_app_status / get_failure_detail  →  Claude 监控
      ↓
（出错时）resolve_intervention / retry_app  →  Claude 决策
```

---

## P0 — 让基本闭环跑通（阻塞）

- [x] **修复截图**：`main.py` 的 `init_framework()` 增加 `controller.init_before_context_run()` 调用，否则截图抓到的是前台窗口而不是游戏
- [ ] **在 Windows 上重启 MCP 服务器**，验证：
  - [ ] `get_screenshot` 能看到真正的游戏画面
  - [ ] `get_game_info` 能拿到体力（当前是 `unable to parse stamina`）
  - [ ] `get_screen_state` 返回的 OCR 是游戏内容
- [ ] **验证 dispatch 链路**：随便启动一个简单 app（比如 `email`），确认：
  - [ ] `start_app` 真的让一条龙跑起来了
  - [ ] `get_app_status` 能看到 running → completed 的状态变化
  - [ ] `get_daily_summary` 完成后正确反映

## P1 — 修掉已知 Bug（影响正确性）

### dispatch.py
- [x] `start_app`：调用 `run_application_async()` 前检查 `z_ctx.ready_for_application`，没就绪就等（框架自己的等待循环被我们绕过了）
- [x] `switch_instance`：切换后补调 `z_ctx.init_for_application()`，否则 map_service/compendium_service 是旧数据

### input.py
- [x] 所有输入方法（click/drag/press_key/scroll/input_text）调用前检查 `controller.is_game_window_ready`，不就绪直接返回错误而不是静默失败
- [x] `scroll` 的 `center_point` fallback 处理，None 时给个默认值或报错

### navigation.py
- [x] `navigate_to_screen` 如果 `current_screen_name` 命中目标，补一次截图验证（现在直接 return success，缓存失效时会骗人）
- [x] 路由遍历循环加最大步数上限，防止路由图有环时死循环
- [x] 最终截图后检查 `final_screen is not None`

### intervention/patches.py
- [x] **验证 `round_result.result == OperationRoundResultEnum.FAIL` 这个判断是对的**（已核对一条龙源码：`OperationRoundResult.result` 的真实类型就是 `OperationRoundResultEnum`，且 `FAIL = -1`）
- [x] `switch_context_pause_and_run()` 调用前检查 `run_context._run_state`，不是 RUNNING 就别暂停
- [x] 截图编码失败时明确返回 None 并 log，不要只 warning

### main.py
- [x] `ctx.init()` 完成后检查 `ready_for_application`，没就绪就 log error（现在静默 fallback）
- [x] 游戏窗口没找到时给出明确的 warning 并提示用户启动游戏

### state/extractor.py
- [x] `extract_equipment` 目前是 stub（只返回 OCR 原文），要么真正解析驱动盘数据（稀有度、主词条、副词条、位置），要么直接去掉这个接口让 Claude 看截图自己判断
- [x] `extract_characters` 补齐：星级、元素、武器类型、技能等级
- [x] `extract_inventory` 补稀有度识别
- [x] OCR 失败时 log 具体哪个服务失败（现在三个 fallback 都静默吞异常）

## P2 — 质量改善（不急但要做）

### 持久化安全
- [ ] `goals/manager.py` 的 YAML 读写加文件锁（并发修改会冲突）
- [ ] `planning/store.py` 同上
- [x] `planning/store.py` 的状态机修正：某一步失败后整个 plan 应该立即转 FAILED，不要卡在 ACTIVE

### 性能
- [ ] `knowledge/service.py` 的 `_search_framework` 加缓存，每次查询都全量遍历框架配置目录太慢
- [ ] `knowledge/rag.py` 的 `build_index` 首次调用时用 `asyncio.to_thread` 包起来，不要阻塞事件循环

### 资源管理
- [ ] `server/event_stream.py` 的 SSE 订阅者断开时自动清理，现在是内存泄漏
- [ ] `intervention/queue.py` 的 timeout 和 late-resolve 之间的竞态条件（需要原子状态转换）

### 诊断
- [ ] `analysis.py` 的日志文件路径写死成 `.log/log.txt`，改成从 framework config 读或允许参数指定
- [ ] `knowledge/service.py` 加载 YAML 失败时 log 具体文件和错误，不要 `except: continue`

## P3 — 战略决策（跟你商量）

### 关于"推图/推剧情/解锁新内容"
**一条龙目前没有主线剧情推进的模块。** 审计结果：

| 模块 | 做什么 |
|------|--------|
| `world_patrol` | 锄大地，跑预设巡逻路线 |
| `withered_domain` | 空洞零 / 枯萎之都 |
| `lost_void` | 空洞零 / 迷失之地 |
| `life_on_line` | 拿命验收（一个特定挑战） |
| `commission_assistant` | 委托助手 |

没有"推主线"的 app。所以你想要的"自动推剧情"需要二选一：

- [ ] **方案 A**：给一条龙提 PR，新写一个 `story_progression` 模块（改动一条龙源码，需要懂它的 operation node 系统）
- [ ] **方案 B**：在 zzz-agent 里做一个"Claude 直接用 click/drag/press_key 操控游戏"的剧情推进工具（完全不依赖一条龙，Claude 看截图 + 输入工具就能推）

我个人建议 **方案 B** —— 不动一条龙源码，把推剧情做成"Claude + input tools"的组合。input.py 现有的工具已经够了，缺的只是让 Claude 有"剧情感知"能力。

### 关于 knowledge / goals / plans 这些"辅助服务"
之前我说它们多余说得太满。重新审查后它们都是 WORKING 且有测试的，保留。但可以考虑：
- [ ] knowledge 的 remote URL 还是 TODO 状态，要么配上要么删掉这一层
- [ ] goals/plans 是否真的需要 YAML 持久化？还是 Claude 每次会话自己记就行？（持久化对跨会话有价值，但增加维护成本）

## P4 — 爱丽丝养成（原始需求）

等 P0 完成后就能做：

- [ ] `get_screenshot` 确认游戏在主界面
- [ ] Claude 用 `click` + `navigate_to` 进入角色面板
- [ ] `get_player_state("characters")` 获取爱丽丝当前等级/突破/技能
- [ ] 查游戏知识（本地 characters.yml 或让 Claude 直接搜网上攻略）确认升级材料需求
- [ ] 根据体力和材料需求，`start_app("charge_plan")` 刷对应副本
- [ ] 刷完材料后 Claude 操控角色面板做升级操作
- [ ] 用 `update_goal` 记录养成进度

---

## 执行顺序建议

1. **现在**：P0 全部跑通（1-2 轮对话）
2. **确认基础可用后**：在 Windows 真机上验证已修好的 P1 主路径（dispatch / input / patches / navigation / extractor）
3. **同时**：做 P4 的爱丽丝养成流程，边跑边暴露更多问题
4. **遇到推剧情需求时**：决定 P3 的方案 A/B
5. **P2 的质量问题**：有空再搞

## 不做的事

- ❌ 不重写一条龙已经有的能力（OCR、模板匹配、节点调度、路由图）
- ❌ 不为了"看起来完整"而加功能（比如把 state_extractor 做成完美解析器）—— Claude 是多模态的，能看截图
- ❌ 不做过度工程（插件系统、事件总线、配置热加载这类）
