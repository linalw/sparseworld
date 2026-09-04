# Isaac Sim 6 仿真验证

本实验用于在只有 Gemini 335、没有移动底盘时验证语义导航软件链路。脚本在本地程序化生成室内走廊、墙体、障碍物、语义目标和运动基座，不依赖 Nucleus 资产下载。

运行：

```bash
cd /home/ubuntu/linalw/Projects/spraseworld/gpt/世界稀疏建模01/.worktrees/codex-live-sparse-mapping
bash scripts/start_isaacsim_local_nav.sh
```

启动脚本使用 Isaac Sim 6 自带的 Python 3.12 Humble ROS 绑定；不要把系统 Python 3.10 的 `rclpy` 混入 Isaac 进程，否则会触发 ABI 崩溃。可选网络代理只影响下载，不影响本地场景。

仿真发布 `/sim/camera/rgb`、`/sim/camera/depth`、`/sim/camera/camera_info`、`/sim/imu`、`/sim/odom` 和 `/tf`，并接收 `/cmd_vel`。四航点路线绕过中间障碍物，结果写入 `artifacts/evidence/isaacsim_local_nav_smoke.json` 及 SHA-256。

2026-09-04 实测：20 秒运行，六类话题各 151 条；四个航点到达；终点误差 `0.07919 m`；碰撞计数 `0`；状态 `executed_unverified`。这是 `simulation_evidence`，控制器为运动学航点控制器，不能推导 Nav2、动力学、真实可通行性、Gemini 335 等价性或安全通过。

后续将由系统 ROS 2 进程通过 DDS 订阅这些话题并录制 MCAP，再把 RGB-D 关键帧接入现有异步语义 worker，最后替换为 Nav2 goal/action 闭环。
