"""Deterministic simulation core for navigation smoke tests."""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class SimulationConfig:
    step_s: float = 0.05
    timeout_s: float = 20.0
    target: tuple[float, float] = (2.0, 0.0)
    max_linear_speed: float = 0.6
    max_angular_speed: float = 1.2
    goal_tolerance_m: float = 0.06
    robot_radius_m: float = 0.18
    obstacles: tuple[tuple[float, float, float, float], ...] = ()
    sensor_width: int = 320
    sensor_height: int = 240
    def __post_init__(self):
        for name in ('step_s','timeout_s','max_linear_speed','max_angular_speed','goal_tolerance_m','robot_radius_m'):
            value=float(getattr(self,name))
            if not math.isfinite(value) or value <= 0: raise ValueError(f'{name} must be positive')
        if len(self.target)!=2 or not all(math.isfinite(float(v)) for v in self.target): raise ValueError('target must contain two finite coordinates')
        if self.sensor_width<=0 or self.sensor_height<=0: raise ValueError('sensor dimensions must be positive')
        for box in self.obstacles:
            if len(box)!=4 or box[0]>box[2] or box[1]>box[3]: raise ValueError('obstacles must be xmin,ymin,xmax,ymax')

@dataclass
class Pose2D:
    x: float=0.0; y: float=0.0; yaw: float=0.0

@dataclass(frozen=True)
class SensorFrame:
    timestamp_s: float; frame_id: str; rgb_shape: tuple[int,int,int]; depth_shape: tuple[int,int]; depth_m: float
    imu_accel_mps2: tuple[float,float,float]; imu_gyro_rps: tuple[float,float,float]
    @classmethod
    def synthetic(cls, timestamp_s, *, width=320, height=240):
        if width<=0 or height<=0: raise ValueError('sensor dimensions must be positive')
        return cls(float(timestamp_s),'camera_link',(height,width,3),(height,width),3.0,(0.0,0.0,9.81),(0.0,0.0,0.0))

class DifferentialDriveSim:
    def __init__(self, config, pose=None):
        self.config=config; self.pose=pose or Pose2D(); self.last_command=(0.0,0.0); self.events=[]; self.collision_count=0; self.path_length_m=0.0; self.elapsed_s=0.0
    def _collides(self,x,y):
        r=self.config.robot_radius_m
        return any(a-r<=x<=c+r and b-r<=y<=d+r for a,b,c,d in self.config.obstacles)
    def step(self, linear_mps, angular_rps):
        requested=(float(linear_mps),float(angular_rps)); linear=max(-self.config.max_linear_speed,min(self.config.max_linear_speed,requested[0])); angular=max(-self.config.max_angular_speed,min(self.config.max_angular_speed,requested[1]))
        if (linear,angular)!=requested: self.events.append('command_clamped')
        ox,oy=self.pose.x,self.pose.y; self.pose.yaw=(self.pose.yaw+angular*self.config.step_s+math.pi)%(2*math.pi)-math.pi; self.pose.x+=linear*math.cos(self.pose.yaw)*self.config.step_s; self.pose.y+=linear*math.sin(self.pose.yaw)*self.config.step_s; self.path_length_m+=math.hypot(self.pose.x-ox,self.pose.y-oy); self.elapsed_s+=self.config.step_s; self.last_command=(linear,angular)
        if self._collides(self.pose.x,self.pose.y): self.collision_count+=1; self.events.append('collision')
        return SensorFrame.synthetic(self.elapsed_s,width=self.config.sensor_width,height=self.config.sensor_height)

def _angle_error(target,current): return (target-current+math.pi)%(2*math.pi)-math.pi

def run_smoke_test(config=None):
    config=config or SimulationConfig(); sim=DifferentialDriveSim(config); trajectory=[]; max_steps=max(1,math.ceil(config.timeout_s/config.step_s))
    for _ in range(max_steps):
        dx,dy=config.target[0]-sim.pose.x,config.target[1]-sim.pose.y; distance=math.hypot(dx,dy)
        if distance<=config.goal_tolerance_m: break
        heading=_angle_error(math.atan2(dy,dx),sim.pose.yaw); linear=min(config.max_linear_speed,1.5*distance)*max(0.0,math.cos(heading)); angular=max(-config.max_angular_speed,min(config.max_angular_speed,2.2*heading)); frame=sim.step(linear,angular); trajectory.append({'t':frame.timestamp_s,'x':sim.pose.x,'y':sim.pose.y,'yaw':sim.pose.yaw})
        if sim.collision_count: return _result(config,sim,'failed_collision',trajectory)
    error=math.hypot(config.target[0]-sim.pose.x,config.target[1]-sim.pose.y); return _result(config,sim,'completed' if error<=config.goal_tolerance_m else 'failed_timeout',trajectory)

def _result(config,sim,status,trajectory):
    return {'evidence_class':'simulation_evidence','status':status,'position_error_m':math.hypot(config.target[0]-sim.pose.x,config.target[1]-sim.pose.y),'path_length_m':sim.path_length_m,'collision_count':sim.collision_count,'replan_count':0,'elapsed_s':sim.elapsed_s,'trajectory':trajectory,'sensor_contract':{'rgb':True,'depth':True,'camera_info':True,'imu':True,'odom':True,'tf':True},'events':list(sim.events)}
