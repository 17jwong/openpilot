#!/usr/bin/env python3
from cereal import car
from openpilot.common.conversions import Conversions as CV
from openpilot.selfdrive.car.mazda.values import CAR, LKAS_LIMITS, GEN2, GEN1
from openpilot.selfdrive.car import get_safety_config
from openpilot.selfdrive.car.interfaces import CarInterfaceBase, TorqueFromLateralAccelCallbackType, FRICTION_THRESHOLD
from openpilot.selfdrive.controls.lib.drive_helpers import get_friction
from openpilot.selfdrive.global_ti import TI
from panda import Panda
from openpilot.common.params import Params

ButtonType = car.CarState.ButtonEvent.Type
EventName = car.CarEvent.EventName

class CarInterface(CarInterfaceBase):
  
  @staticmethod
  def torque_from_lateral_accel_mazda(lateral_accel_value: float, torque_params: car.CarParams.LateralTorqueTuning,
                                           lateral_accel_error: float, lateral_accel_deadzone: float,
                                           steering_angle: float, vego: float, friction_compensation: bool) -> float:
    steering_angle = abs(steering_angle)
    if Params().get_bool("ManualTorqueTune"):
      laf = Params().get_float("LatAngleFactor")
    else:
      laf = Params().get_float("LatAngleFactorStock")
    lat_factor = torque_params.latAccelFactor * ((steering_angle * laf) + 1)
    
    friction = get_friction(lateral_accel_error, lateral_accel_deadzone, FRICTION_THRESHOLD, torque_params, friction_compensation)
    return float(lateral_accel_value / lat_factor) + friction

  def torque_from_lateral_accel(self) -> TorqueFromLateralAccelCallbackType:
    if self.CP.carFingerprint in GEN2:
      return self.torque_from_lateral_accel_mazda
    else:
      return self.torque_from_lateral_accel_linear

  @staticmethod
  def _get_params(ret, candidate, fingerprint, car_fw, experimental_long, docs):
    ret.carName = "mazda"
    p = Params()
    if candidate in GEN1:
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.mazda)]
      ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_ENABLE_TI
      ret.steerActuatorDelay = 0.1
      p.put_float("LatAngleFactorStock", .0)
      
    if candidate in GEN2:
      ret.experimentalLongitudinalAvailable = True
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.mazda2019)]
      ret.openpilotLongitudinalControl = experimental_long
      ret.stopAccel = -.5
      ret.vEgoStarting = .2
      ret.longitudinalTuning.kpBP = [0., 5., 35.]
      ret.longitudinalTuning.kpV = [0.0, 0.0, 0.0]
      ret.longitudinalTuning.kiBP = [0., 35.]
      ret.longitudinalTuning.kiV = [0.1, 0.1]
      ret.startingState = True
      ret.steerActuatorDelay = 0.3
      p.put_float("LatAngleFactorStock", .14)
      
    ret.radarUnavailable = True

    ret.dashcamOnly = False

    
    ret.steerLimitTimer = 1.0
    ret.tireStiffnessFactor = 1.0   # not optimized yet

    CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)

    if candidate in (CAR.CX5, CAR.CX5_2022):
      ret.mass = 3655 * CV.LB_TO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 15.5
    elif candidate in (CAR.CX9, CAR.CX9_2021):
      ret.mass = 4217 * CV.LB_TO_KG
      ret.wheelbase = 3.1
      ret.steerRatio = 17.6
    elif candidate == CAR.MAZDA3:
      ret.mass = 2875 * CV.LB_TO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 14.0
    elif candidate == CAR.MAZDA6:
      ret.mass = 3443 * CV.LB_TO_KG
      ret.wheelbase = 2.83
      ret.steerRatio = 15.5
    elif candidate in CAR.MAZDA3_2019:
      ret.mass = 3000 * CV.LB_TO_KG
      ret.wheelbase = 2.725
      ret.steerRatio = 17.0
      #ret.lateralTuning.torque.latAngleFactor = .14
    elif candidate in (CAR.CX_30, CAR.CX_50):
      ret.mass = 3527 * CV.LB_TO_KG
      ret.wheelbase = 2.814 # Measured
      ret.steerRatio = 15.5
      ret.steerActuatorDelay = 0.35
      #ret.lateralTuning.torque.latAngleFactor = .14
    elif candidate in (CAR.CX_60, CAR.CX_80, CAR.CX_70, CAR.CX_90):
      ret.mass = 4217 * CV.LB_TO_KG
      ret.wheelbase = 3.1
      ret.steerRatio = 17.6
      #ret.lateralTuning.torque.latAngleFactor = .14

    if candidate not in (CAR.CX5_2022, CAR.MAZDA3_2019, CAR.CX_30, CAR.CX_50, CAR.CX_60, CAR.CX_70, CAR.CX_80, CAR.CX_90):
      ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS

    ret.centerToFront = ret.wheelbase * 0.41

    return ret

  # returns a car.CarState
  def _update(self, c):
    if self.CP.carFingerprint in GEN1:
      if self.CP.enableTorqueInterceptor and not TI.enabled:
        TI.enabled = True
        self.cp_body = self.CS.get_body_can_parser(self.CP)
        self.can_parsers = [self.cp, self.cp_cam, self.cp_adas, self.cp_body, self.cp_loopback]

    ret = self.CS.update(self.cp, self.cp_cam, self.cp_body)

    # events
    events = self.create_common_events(ret)
    if self.CP.carFingerprint in GEN1:
      if self.CS.lkas_disabled:
        events.add(EventName.lkasDisabled)
      elif self.CS.low_speed_alert:
        events.add(EventName.belowSteerSpeed)

      if not self.CS.acc_active_last and not self.CS.ti_lkas_allowed:
        events.add(EventName.steerTempUnavailable)

    ret.events = events.to_msg()

    return ret

  def apply(self, c, now_nanos, sport_plus):
    return self.CC.update(c, self.CS, now_nanos)
