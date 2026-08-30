# 新对话交接包：world_sparse_semantic_mapping

- 交接日期：2026-08-29
- 项目状态：`proposal_ready; prototype_validation_pending`
- 当前阶段：技术方案、数据模型和 P0 采集/分析适配器已经完成；video 组权限已生效并完成一次 30 秒真实 Gemini 335 时间戳采集，但标定、同步、rosbag 与硬件性能验证仍未完成。
- 推荐接手目标：完成 video/udev 权限与新登录后，获取可重复的室内 ROS 2 数据集，并完成 P0/P1 标定、定位和静态障碍导航验证。

## 1. 这份交接包的用途

本文件供全新的 Codex 对话直接读取。接手者应从已有方案进入原型验证，不要重新从“点云是否需要”“稀疏/稠密点云如何分工”等概念讨论开始，也不要把尚未实测的指标表述为已经实现的性能。

项目工作区根目录：

`E:\project\世界稀疏建模\世界稀疏建模01`

项目记录目录：

`E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records`

## 2. 已冻结的架构基线

系统采用四层世界模型，而不是保存一张永久稠密三维点云：

1. **度量定位层**：RGB-D 双目相机、IMU、稀疏自然特征地标、关键帧、回环与位姿图/因子图优化，用于估计 `map -> odom -> base_link` 位姿和协方差。
2. **语义对象与地点层**：房间、门、走廊、物体及其语义、外观属性、锚点、几何、置信度、观测证据和生命周期。
3. **持久通行拓扑层**：房间、门、转弯点、楼梯、电梯等节点和结构连通边，用于全局路线搜索。
4. **瞬时稠密安全层**：由当前 RGB-D 深度实时生成的局部 2D/3D costmap，用于碰撞检查、局部绕障、到达目标前再确认和精细操作；它具有局部原点、时间戳和 TTL，不应作为永久全楼稠密地图保存。

核心坐标系和接口：`map -> odom -> base_link -> camera_link/imu_link`；统一 SI 单位（米、弧度）；同步 RGB、左右目、深度与 IMU 时间戳；位姿数据附带 `6x6` 协方差。

## 3. 不要重新作出的关键决策

- 正常室内 SLAM **不强制**布设已知标记物。墙角、门框、纹理和稳定家具等自然特征可用于建图和重定位；回环加全局优化用于压制累计漂移。
- IMU、轮速/视觉里程计和相邻帧相对观测不能独自消除全局漂移；它们应作为带不确定度的约束因子，而非无条件累积的位置增量。
- 如果需要测量意义上的建筑/世界绝对坐标，或环境长期弱纹理、重复纹理、动态变化明显，则需要可选外部基准，如测量控制点、AprilTag、UWB、GNSS（室外）等。
- 物体数据不能只保存“四个角点加一个内部点”。该粗略字段可以保留，但持久对象还应保留 `anchor_xyz`、候选语义、属性、置信度、观测截图，必要时增加 AABB/OBB、footprint、表面角点、法向量和协方差。
- 物体的物理可移动性（如 `static`、`movable`）与观测生命周期（如 `tentative`、`confirmed`、`moved`）必须分开表达。
- 全局路线走拓扑图上的 Dijkstra/A*；是否能在此刻通过必须由实时局部深度/costmap 决定。每条拓扑边都应有 `structurally_connected` 与 `requires_realtime_clearance_check=true`。
- 多层建筑不可压成一张无区别的二维图。每层保有 `floor_id`、本层二维区域地图和度量 `z` 范围；楼梯/电梯是跨楼层图边。

## 4. 语言导航闭环

对于“去找红色的水杯”这类请求，系统流程已确定为：

1. 解析目标类别、属性和地点等约束。
2. 在语义对象图中检索候选物体，并按照类别、颜色/视觉证据、最近观测时间、地点和置信度排序。
3. 对候选物体关联的可观测目标位姿规划全局路线和局部路径。
4. 到达后用实时视觉重新确认；遮挡、物体移动或没有匹配时，报告不确定性或切换候选，而不是盲目声称已找到。

“从书房到卧室”可由地点/房间语义解析为拓扑图中的起点和终点；不要求用户报出坐标。若地点语义还未建立，系统才应请求用户示教、选择地图目标或给出坐标。

## 5. 已有交付物

优先阅读顺序如下：

| 作用 | 绝对路径 | 说明 |
|---|---|---|
| 主技术方案 | `E:\project\世界稀疏建模\世界稀疏建模01\docs\semantic_world_model_proposal.md` | 架构、推导、算法链路、实施阶段、风险与验证门槛的主来源 |
| PDF 方案 | `E:\project\世界稀疏建模\世界稀疏建模01\outputs\semantic_world_model_proposal.pdf` | 已渲染并逐页目检，共 13 页 |
| Word 方案 | `E:\project\世界稀疏建模\世界稀疏建模01\outputs\semantic_world_model_proposal.docx` | 已生成且 OOXML 结构检查通过；视觉渲染 QA 尚未完成 |
| 数据结构 | `E:\project\世界稀疏建模\世界稀疏建模01\schemas\semantic_world_model.schema.json` | 世界模型 JSON Schema |
| 示例数据 | `E:\project\世界稀疏建模\世界稀疏建模01\schemas\semantic_world_model.example.json` | 与 schema 对齐的 JSON 示例 |
| 当前状态 | `E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\CURRENT_STATE.md` | 当前阶段和下一行动 |
| 架构决策 | `E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\DECISIONS.md` | 已锁定的 D-001 至 D-007 |
| 验证矩阵 | `E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\VERIFICATION.md` | V-001 至 V-010 的权威范围清单 |
| 问题与恢复 | `E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\ERRORS.md` | 已知环境限制 |
| 历史交接索引 | `E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\HANDOFF.md` | 跨学科接口和未冻结项 |

## 6. 已完成的验证与未验证边界

**已经完成：**

- 技术方案、JSON Schema 和示例世界模型已形成一致的概念设计。
- PDF 已重新构建、渲染，并完成 13 页的视觉检查。
- DOCX 已成功生成，且通过 OOXML 结构和内容一致性检查。
- Schema 与示例 JSON 均已成功解析。

**尚未完成，不能对外称为已达到：**

- 标准 JSON Schema 校验：本地没有可用的标准校验器，尚未在 CI 或运行时校验。
- DOCX 页面对齐、断页和图片视觉检查：本地没有 LibreOffice/`soffice`。
- 硬件指标：ATE/RPE、回环/重定位成功率、语义关联精度、跨楼层过渡、障碍漏检率、端到端延迟、停止行为和故障恢复，均未在真实机器人上测量。

接手者必须以 `VERIFICATION.md` 为范围基准，并在每项实测后更新证据、配置、原始数据位置和结论。

## 7. P0/P1 的下一步工作

### 已执行的 P0 前置检查（2026-08-29）

- 已在 `sparseworld` 中安装并导入 `pyorbbecsdk2==2.1.2`（导入名 `pyorbbecsdk`）；下载 wheel SHA-256 为 `e1d3e207995ac60e2bf3350086777df1ba15669a41c6dcfb81c0d896cbb17fcb`。
- SDK 能发现 1 个 Gemini 335；历史运行曾因 Access denied（SDK status 113）失败。当前用户已属于 `video` 组，`/dev/video0` 至 `/dev/video7` 为 `root:video`；2026-08-30 已完成真实组合流时间戳采集。
- 采集适配器按 fail-closed 规则写出了零样本 `failed_incomplete` manifest；证据为 `artifacts/evidence/p0_capture_preflight_20260829T024616Z/capture_manifest.json` 和 `Log/OrbbecSDK.log.txt`。这证明权限前置条件未满足，不是相机质量、标定、同步或性能结论。
- 历史权限阻塞已经解除并完成了权限恢复后的 30 秒静止采集；禁止为绕过后续 ROS/标定前置条件改用未配置的设备或伪造数据。
- 已完成权限恢复后的 30 秒采集；下一步是按 `CALIBRATION_AND_TIME_SYNC.md` 完成标定/同步检查，并按 `INDOOR_ROSBAG_PROTOCOL.md` 采集可回放 rosbag。当前采集证据仍标记为 `captured_unassessed`。
- 已完成冻结 IMU profile 的 5 秒硬件复核：accel 200 Hz/`ACCEL_FS_4g`、gyro 200 Hz/`FS_1000dps`；证据位于 `artifacts/evidence/p0_explicit_imu_profile_validated_20260830T070442Z/`，profile SHA-256 为 `fbedc5f15e891af147b560ac12c386e22c35dc8f905e340718275992493e851e`。这仍是 profile/可观测性证据，不是标定或同步通过。
- `sparseworld-p0 assess` 已对 `p0_depth_quality_capture_20260830T072043Z` 重新生成确定性报告，报告 SHA-256 为 `c771ece64d5c08a68271ddb4823083dad1cbfbc55f4bb698f0c76a3c857f9a9e`；平均深度有效率为 `0.4509053164`（134 帧），总体 `not_measured`。最新软件验证为 54 个测试通过、`pip check` 无损坏依赖。

### P0：可观测性与标定基线

1. 冻结并记录相机型号、分辨率、帧率、基线、深度范围、IMU 量程/频率、机器人底盘尺寸、最小通行净空、计算平台/GPU、供电/热限制、ROS 2 发行版和消息版本。
2. 完成相机内参、左右目外参、相机-IMU 外参和时间偏移标定；保存原始标定文件、工具版本、日期和残差。
3. 设计一条包含门框、转弯、纹理丰富/贫乏区、回到起点的可重复室内路线，采集带完整时间戳的 rosbag。
4. 在 rosbag 回放中检查传感器频率、时间同步、丢帧、曝光/运动模糊、深度有效范围和 IMU 饱和；形成数据质量报告。
5. 明确 `map` 原点定义。没有外部测量基准时，原点只是首次可靠初始化时的局部坐标，不应标为建筑测量坐标。

P0 退出条件：标定和时间同步可以复现；一条可回放数据集可稳定运行；数据质量问题有记录和处置结论。

### P1：单层定位与静态障碍导航

1. 选择并集成可回放的视觉惯性 SLAM/里程计基线，输出位姿、关键帧、稀疏地标、协方差和回环事件。
2. 用独立参考轨迹或可审计的人工基准评估 ATE/RPE；若没有真值，明确写“相对一致性评估”，不得伪称绝对精度。
3. 从静态结构提取或人工审核房间、门、走廊和转弯点，建立单层拓扑图；每一边都落实实时净空检查契约。
4. 由实时 RGB-D 生成局部 costmap，验证全局路径跟随、动态障碍停止/绕行、门口与狭窄区的协方差/净空门控。
5. 记录失败案例：弱纹理、重复纹理、动态人群、遮挡、玻璃/反光、深度缺失和回环误匹配，并实现降级、停车或请求协助行为。

P1 退出条件：在指定单层路线完成可重复定位、回环/重定位演示和静态/动态障碍安全执行；所有数值连同测试配置、原始数据和失败案例记录进入 `VERIFICATION.md`。

## 8. 接手时的工作原则

- 先阅读方案第 3、4、7、10、12、13、14 节，以及项目记录中的 `CURRENT_STATE.md`、`DECISIONS.md`、`VERIFICATION.md`。
- 先检查工作区现状，避免覆盖用户随后新增的文件或配置；当前目录不是 Git 仓库。
- 用 `apply_patch` 进行人工文本/代码编辑；保留历史记录，不删除既有方案。
- 新的工程事实、配置和测试证据应写回项目记录；设计决策变化则追加到 `DECISIONS.md`，不要静默改写已冻结决策。
- 涉及人员、移动机器人或真实设备试验时，先定义安全边界、急停/限速、测试区域和人工监护；传感器不确定性高时应减速、停车或请求协助。

## 9. 可直接粘贴到新对话的提示词

```text
请继续下面的机器人语义世界稀疏建模项目。工作区为：
E:\project\世界稀疏建模\世界稀疏建模01

先阅读以下交接文件和权威验证清单：
1. E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\NEW_CONVERSATION_HANDOFF.md
2. E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\CURRENT_STATE.md
3. E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\DECISIONS.md
4. E:\project\世界稀疏建模\世界稀疏建模01\engineering_projects\world_sparse_semantic_mapping\project_records\VERIFICATION.md
5. E:\project\世界稀疏建模\世界稀疏建模01\docs\semantic_world_model_proposal.md

项目仍处于“proposal_ready; prototype_validation_pending”。请不要把概念设计或文档检查说成硬件性能已经验证。沿用已冻结的四层架构和 D-001 至 D-007 决策，优先启动 P0：冻结传感器/计算配置、定义并执行标定与时间同步检查、设计可重复的室内 rosbag 采集和质量评估。完成后更新项目记录，并给出可审计的验证证据和未解决风险。
```

## 10. 交接完成判定

新对话应能仅依赖本文件和列出的路径，准确回答：项目目前处于什么阶段、哪些架构决定已固定、哪些性能还没有实测、下一步先做什么、以及证据要写到哪里。若上述任一项发生变化，请同步更新本文件、`CURRENT_STATE.md` 与相应的决策/验证记录。
