# 实时稀疏语义建图模式实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有本机采集控制台中新增低存储实时稀疏建图模式：连续显示 RGB-D/SLAM 状态，仅对受控关键帧异步执行语义识别。

**Architecture:** `LiveMappingSession` 管理 ROS 驱动、RTAB-Map（可选依赖）、关键帧门控和单槽语义 worker；FastAPI 扩展模式、状态、地图和对象接口；前端增加模式选择、实时指标和对象列表。无 RTAB-Map/模型时 fail-closed 显示 unavailable，不伪造轨迹或地图。

**Tech Stack:** Python 3.10、FastAPI/Uvicorn、ROS 2 Humble、RTAB-Map ROS、现有 semantic mapping 后端、vanilla JavaScript。

**Spec:** `docs/superpowers/specs/2026-09-02-live-sparse-semantic-mapping-design.md`

## Global Constraints

- 实时模式默认不录制完整 rosbag；只有显式启用 debug bag 才录制。
- 语义关键帧默认至少间隔 1 秒，或位移 0.35 m，或转角 15°。
- 语义队列容量固定为 1，新关键帧覆盖旧任务；worker 不阻塞 SLAM/UI。
- 对象状态必须标记 `observed_in_live_map` 与 `global_accuracy: unvalidated`。
- 不控制底盘；不把实时链路证据宣称为标定、同步、SLAM、导航或安全验收。

### Task 1: 关键帧门控与单槽语义队列

**Files:**
- Create: `src/sparseworld_p0/live_mapping.py`
- Test: `tests/test_live_mapping.py`

**Interfaces:** `KeyframeGate.accept(timestamp, position, yaw) -> bool`; `LatestFrameQueue.put(frame) -> None`; `LatestFrameQueue.get() -> frame | None`; `LiveSemanticWorker.snapshot() -> dict`。

- [ ] 写失败测试覆盖时间/位移/旋转门控、队列覆盖和 worker 状态。
- [ ] 实现纯 Python 门控与条件变量队列；队列长度固定 1。
- [ ] 接入已有 `build_semantic_map`/backend 适配器的最小 worker 接口，推理失败记录错误而不阻塞生产者。
- [ ] 测试关键帧计数、丢弃计数、处理耗时和停止行为。
- [ ] 运行 `conda run -n sparseworld python -m pytest -q tests/test_live_mapping.py`。

### Task 2: ROS 实时会话与 RTAB-Map 命令编排

**Files:**
- Modify: `src/sparseworld_p0/capture_console.py`
- Test: `tests/test_capture_console.py`

**Interfaces:** `CaptureSession.start(mode="capture"|"live", debug_bag=False, ...)`; `snapshot()` 返回 `mode`, `slam_status`, `keyframes`, `semantic_worker`, `storage_policy`。

- [ ] 写 fake subprocess 测试验证 live 模式不生成 rosbag 命令，debug_bag 才生成。
- [ ] 编排官方 Orbbec 驱动、RTAB-Map launch 和可选 debug bag；所有命令写入 manifest。
- [ ] 检查 `rtabmap_ros`/`rtabmap` 可执行文件和 `/dev/video*`，缺失时返回明确 `unavailable`。
- [ ] 在 session 停止时按 worker → RTAB-Map → driver 顺序退出，保存地图/对象快照路径。
- [ ] 运行控制器回归测试。

### Task 3: FastAPI 实时模式 API

**Files:**
- Modify: `src/sparseworld_p0/capture_console_api.py`
- Test: `tests/test_capture_console_api.py`

**Interfaces:** `POST /api/start` 接受 `{mode, debug_bag, run_name, duration_s}`；`GET /api/status`；`GET /api/map/preview`；`GET /api/objects`。

- [ ] 写 API 测试覆盖模式校验、实时状态字段和对象列表。
- [ ] 实现实时模式启动冲突/依赖错误的 400/409 响应。
- [ ] 将地图预览和对象 JSON 限制在当前 run 目录内，路径穿越返回 400。
- [ ] 保持旧采集 API 向后兼容。

### Task 4: 前端实时地图视图

**Files:**
- Modify: `src/sparseworld_p0/static/capture_console.html`
- Modify: `src/sparseworld_p0/static/capture_console.js`
- Modify: `src/sparseworld_p0/static/capture_console.css`
- Test: `tests/test_capture_console_ui.py`

- [ ] 增加“采集模式/实时建图模式”选择和“同时录制 debug bag”复选框。
- [ ] 实时模式显示 SLAM 状态、关键帧接受/丢弃、语义队列、存储策略、地图预览和对象列表。
- [ ] 对 `unavailable`、`unvalidated` 和输入断流显示中文告警。
- [ ] 模式切换/录制中禁用互斥控件，停止后保留历史入口。
- [ ] 运行 UI 静态资源测试。

### Task 5: 文档、证据和发布

**Files:**
- Create: `docs/p0/LIVE_SPARSE_MAPPING.md`
- Modify: `README.md`
- Modify: `engineering_projects/world_sparse_semantic_mapping/project_records/CURRENT_STATE.md`
- Modify: `engineering_projects/world_sparse_semantic_mapping/project_records/VERIFICATION.md`

- [ ] 记录安装 RTAB-Map、模型缓存、启动命令、关键帧策略和存储估算。
- [ ] 用 dry-run 验证 live 命令编排；若依赖可用，进行短时人工监护硬件 smoke run。
- [ ] 保存状态/manifest/API 测试证据；明确该证据仍不是硬件性能验收。
- [ ] 运行 `pytest`、`pip check`、`git diff --check`，提交并推送 `codex/live-sparse-mapping`。
