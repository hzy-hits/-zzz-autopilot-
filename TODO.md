# ZZZ-Agent TODO

## 战略方向

Claude 做大脑（规划 + 调度），一条龙做手脚（执行自动化模块）。
**在 App 层级调度，不做底层交互。**

一条龙是为"专注自动化运行"设计的：启动 app → 游戏到前台 → 一条龙接管截图/OCR/导航/按键 → 运行完毕 → 用户取回控制。
Claude 的角色是**选择跑哪个 app、监控结果、处理失败**，不是逐帧截图、逐键操控游戏。

核心闭环：
```
list_available_apps / get_daily_summary  →  Claude 选模块
      ↓
start_app(app_id)  →  一条龙接管游戏（自动前台、自动截图、自动操作）
      ↓
get_app_status / get_app_execution_log  →  Claude 监控
      ↓
（出错时）get_failure_detail / resolve_intervention / retry_app  →  Claude 决策
      ↓
get_daily_summary  →  确认完成
```

### 关于截图和底层输入

- 一条龙的截图（PrintWindow/BitBlt）在 ZZZ 后台不可靠，**只有游戏在前台时才能截到**
- Windows 的焦点保护机制会拒绝 `win.activate()`（ACCESS_DENIED），无法可靠地在代码里把游戏推到前台
- **因此**：截图/OCR/底层输入不适合做"交互式探索"（单屏用户会冲突），只适合一条龙 App 运行期间的内部使用
- 如果将来需要后台截图，唯一可靠方案是 Windows Graphics Capture API（WGC），但那是一个独立项目

### 不做的事

- ❌ 不在 MCP 层重写截图/OCR/输入/导航（一条龙 App 内部自己处理）
- ❌ 不试图强行拉游戏到前台（active() 会被 Windows 拒绝）
- ❌ 不做 background_mode 魔改（半解决问题，增加复杂度）
- ❌ 不为了"看起来完整"而加功能
- ❌ 不做过度工程（插件系统、事件总线、配置热加载）

---

## P0 — 验证 App 调度链路

- [x] 框架初始化：`init_before_context_run()` 绑定游戏窗口
- [x] 框架就绪检查：`ready_for_application` 验证
- [ ] **验证 dispatch**：启动一个简单 app（比如 `email`），确认：
  - [ ] `start_app("email")` 让一条龙跑起来
  - [ ] `get_app_status("email")` 能看到 running → completed
  - [ ] `get_daily_summary` 完成后正确反映
- [ ] **验证 intervention**：让一条龙跑一个可能失败的 app，确认 `get_pending_interventions` 能收到请求

## P1 — 已完成的代码修复

> 这些在之前的 commit 里已全部落地，35 测试通过。

- [x] dispatch.py: `ready_for_application` 等待、`switch_instance` 后 `init_for_application()`
- [x] input.py: `is_game_window_ready` 前置检查、scroll fallback
- [x] navigation.py: 截图验证、步数上限、None 检查
- [x] patches.py: 枚举路径验证、运行状态保护、截图失败日志
- [x] state/extractor.py: characters/equipment/inventory 解析、OCR 错误透出
- [x] planning/store.py: 失败步骤立即转 FAILED

## P2 — 质量改善（有空再搞）

- [ ] `goals/manager.py` + `planning/store.py` YAML 读写加文件锁
- [ ] `knowledge/service.py` 的 `_search_framework` 加缓存
- [ ] `knowledge/rag.py` 的 `build_index` 用 `asyncio.to_thread` 包
- [ ] `server/event_stream.py` SSE 订阅者断连清理
- [ ] `intervention/queue.py` timeout/late-resolve 竞态
- [ ] `analysis.py` 日志文件路径可配置
- [ ] `knowledge/service.py` YAML 加载失败 log 具体错误

## P3 — 战略决策

### 推图/推剧情
一条龙没有主线剧情推进模块。如果需要：
- **方案 A**：给一条龙提 PR 写 `story_progression` 模块
- **方案 B**：等 WGC 实现后，用 Claude + input tools 推（需后台截图能力）
- 两者都是大活儿，目前先搁置

### knowledge / goals / plans 辅助服务
- 代码都 WORKING 且有测试，保留
- knowledge remote URL 还是占位符，不急
- goals/plans 的 YAML 持久化对跨会话有价值，保留

## P4 — 爱丽丝养成（原始需求）

**正确路径**：不用 Claude 操控游戏 UI，用一条龙的 App 自动刷材料。

1. [ ] 用户手动看一眼爱丽丝等级 / 突破 / 技能，告诉 Claude
2. [ ] Claude 查攻略确认需要什么材料（哪个副本）
3. [ ] 配置 `charge_plan` 的刷本目标（对应副本 + 次数）
4. [ ] `start_app("charge_plan")` → 一条龙自动刷材料（游戏全屏接管）
5. [ ] `get_app_status` 监控完成情况
6. [ ] 用户手动在游戏里做升级操作（点按钮 = 不可自动化的部分）
7. [ ] 重复 3-6 直到爱丽丝满级

---

## 执行顺序

1. **现在**：P0 验证 dispatch 链路（start_app → status → summary）
2. **P0 通过后**：P4 爱丽丝养成（用户给信息 → Claude 规划 → charge_plan 刷材料）
3. **有空时**：P2 质量改善
4. **将来如果要做交互式操控**：实现 WGC 后台截图，然后重新考虑 P3
