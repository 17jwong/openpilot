#!/usr/bin/env python3
from cereal import car, custom
from panda import Panda
from openpilot.common.conversions import Conversions as CV
from openpilot.selfdrive.car.mazda.values import CAR, LKAS_LIMITS, MazdaFlags, GEN1, GEN2, Buttons
from openpilot.selfdrive.car import create_button_events, get_safety_config
from openpilot.selfdrive.car.interfaces import CarInterfaceBase
from openpilot.common.params import Params

ButtonType = car.CarState.ButtonEvent.Type
FrogPilotButtonType = custom.FrogPilotCarState.ButtonEvent.Type
EventName = car.CarEvent.EventName
BUTTONS_DICT = {Buttons.SET_PLUS: ButtonType.accelCruise, Buttons.SET_MINUS: ButtonType.decelCruise,
                Buttons.RESUME: ButtonType.resumeCruise, Buttons.CANCEL: ButtonType.cancel}

params_memory = Params("/dev/shm/params")

class CarInterface(CarInterfaceBase):

  @staticmethod
  def _get_params(ret, candidate, fingerprint, car_fw, disable_openpilot_long, experimental_long, docs, params):
    ret.carName = "mazda"
    ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.mazda)]
    ret.radarUnavailable = True

    ret.dashcamOnly = False
    ret.openpilotLongitudinalControl = True
    if candidate in GEN1:
      ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_GEN1
      p = Params()
      if p.get_bool("TorqueInterceptorEnabled"): # Torque Interceptor Installed
        print("Torque Interceptor Installed")
        ret.flags |= MazdaFlags.TORQUE_INTERCEPTOR.value
        ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_TORQUE_INTERCEPTOR
      if p.get_bool("RadarInterceptorEnabled"): # Radar Interceptor Installed
        ret.flags |= MazdaFlags.RADAR_INTERCEPTOR.value
        ret.experimentalLongitudinalAvailable = True
        ret.radarUnavailable = False
        ret.startingState = True
        ret.longitudinalTuning.kpBP = [0., 5., 30.]
        ret.longitudinalTuning.kpV = [1.3, 1.0, 0.7]
        ret.longitudinalTuning.kiBP = [0., 5., 20., 30.]
        ret.longitudinalTuning.kiV = [0.36, 0.23, 0.17, 0.1]
        ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_RADAR_INTERCEPTOR

      if p.get_bool("NoMRCC"): # No Mazda Radar Cruise Control; Missing CRZ_CTRL signal
        ret.flags |= MazdaFlags.NO_MRCC.value
        ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_NO_MRCC
      if p.get_bool("NoFSC"):  # No Front Sensing Camera
        ret.flags |= MazdaFlags.NO_FSC.value
        ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_NO_FSC

      ret.steerActuatorDelay = 0.1

    if candidate in GEN2:
      ret.safetyConfigs[0].safetyParam |= Panda.FLAG_MAZDA_GEN2
      ret.experimentalLongitudinalAvailable = True
      ret.stopAccel = -.5
      ret.stoppingDecelRate = 0.1
      ret.vEgoStarting = .1
      ret.vEgoStopping = .1
      # ret.longitudinalTuning.kpBP = [0., 5., 35.]
      # ret.longitudinalTuning.kpV = [0.0, 0.0, 0.0]
      # ret.longitudinalTuning.kiBP = [0., 35.]
      # ret.longitudinalTuning.kiV = [0.1, 0.1]
      ret.longitudinalTuning.kpV = [0]
      ret.longitudinalTuning.kiV = [1.0]
      ret.startingState = True
      ret.steerActuatorDelay = 0.35

      if Params().get_bool("CSLCEnabled"):
        # Used for CEM with CSLC
        ret.openpilotLongitudinalControl = True
        ret.longitudinalTuning.deadzoneBP = [0.]
        ret.longitudinalTuning.deadzoneV = [0.9]  # == 2 mph allowable delta
        ret.stoppingDecelRate = 4.5  # == 10 mph/s
        #ret.longitudinalActuatorDelayLowerBound = 1.
        #ret.longitudinalActuatorDelayUpperBound = 2.

        ret.longitudinalTuning.kpBP = [8.94, 7.2, 28.]  # 8.94 m/s == 20 mph
        ret.longitudinalTuning.kpV = [0., 4., 2.]  # set lower end to 0 since we can't drive below that speed
        ret.longitudinalTuning.kiBP = [0.]
        ret.longitudinalTuning.kiV = [0.1]

    ret.steerLimitTimer = 1.0

    CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)

    #Lateral Tuning changes
    ret.lateralTuning.torque.kp = 0.85

    if candidate not in (CAR.MAZDA_CX5_2022, CAR.MAZDA_3_2019, CAR.MAZDA_CX_30, CAR.MAZDA_CX_50) and not ret.flags & MazdaFlags.TORQUE_INTERCEPTOR:
      ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS

    ret.centerToFront = ret.wheelbase * 0.41

    return ret

  # returns a car.CarState
  def _update(self, c, frogpilot_toggles):
    ret, fp_ret = self.CS.update(self.cp, self.cp_cam, self.cp_body, frogpilot_toggles)
     # TODO: add button types for inc and dec
    ret.buttonEvents = [
      *create_button_events(self.CS.cruise_buttons, self.CS.prev_cruise_buttons, BUTTONS_DICT),
      *create_button_events(self.CS.distance_button, self.CS.prev_distance_button, {1: ButtonType.gapAdjustCruise}),
      *create_button_events(self.CS.lkas_enabled, self.CS.lkas_previously_enabled, {1: FrogPilotButtonType.lkas}),
    ]

    # events
    events = self.create_common_events(ret)

    if self.CP.flags & MazdaFlags.GEN1:
      if self.CS.lkas_disabled:
        events.add(EventName.lkasDisabled)
      elif self.CS.low_speed_alert:
        events.add(EventName.belowSteerSpeed)

      if not self.CS.acc_active_last and not self.CS.ti_lkas_allowed:
        events.add(EventName.steerTempUnavailable)
      #if (not self.CS.ti_lkas_allowed) and (self.CP.flags & MazdaFlags.TORQUE_INTERCEPTOR):
      #  events.add(EventName.steerTempUnavailable) # torqueInterceptorTemporaryWarning

    if params_memory.get_int("Coasting"):
      events.add(EventName.resumeRequired)

    ret.events = events.to_msg()

    return ret, fp_ret
