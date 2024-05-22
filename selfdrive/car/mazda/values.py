from dataclasses import dataclass, field
from enum import StrEnum, IntFlag
from typing import Dict, List, Union

from cereal import car
from openpilot.selfdrive.car import dbc_dict
from openpilot.selfdrive.car.docs_definitions import CarHarness, CarInfo, CarParts
from openpilot.selfdrive.car.fw_query_definitions import FwQueryConfig, Request, StdQueries

Ecu = car.CarParams.Ecu

# Steer torque limits
class CarControllerParams:
  def __init__(self, CP):
    self.STEER_STEP = 1 # 100 Hz
    if CP.carFingerprint in GEN1:
      self.STEER_MAX = 600                # theoretical max_steer 2047
      self.STEER_DELTA_UP = 10             # torque increase per refresh
      self.STEER_DELTA_DOWN = 25           # torque decrease per refresh
      self.STEER_DRIVER_ALLOWANCE = 15     # allowed driver torque before start limiting
      self.STEER_DRIVER_MULTIPLIER = 40     # weight driver torque
      self.STEER_DRIVER_FACTOR = 1         # from dbc
      self.STEER_ERROR_MAX = 350           # max delta between torque cmd and torque motor
      
      self.TI_STEER_MAX = 600                # theoretical max_steer 2047
      self.TI_STEER_DELTA_UP = 6             # torque increase per refresh
      self.TI_STEER_DELTA_DOWN = 15           # torque decrease per refresh
      self.TI_STEER_DRIVER_ALLOWANCE = 15    # allowed driver torque before start limiting
      self.TI_STEER_DRIVER_MULTIPLIER = 40     # weight driver torque
      self.TI_STEER_DRIVER_FACTOR = 1         # from dbc
      self.TI_STEER_ERROR_MAX = 350           # max delta between torque cmd and torque motor
    if CP.carFingerprint in GEN2:
      self.STEER_MAX = 8000                 
      self.STEER_DELTA_UP = 45              # torque increase per refresh
      self.STEER_DELTA_DOWN = 80            # torque decrease per refresh
      self.STEER_DRIVER_ALLOWANCE = 1400     # allowed driver torque before start limiting
      self.STEER_DRIVER_MULTIPLIER = 5      # weight driver torque
      self.STEER_DRIVER_FACTOR = 1           # from dbc
      self.STEER_ERROR_MAX = 3500            # max delta between torque cmd and torque motor

class MazdaFlags(IntFlag):
  TORQUE_INTERCEPTOR = 1
  RADAR_INTERCEPTOR = 2

class TI_STATE:
  DISCOVER = 0
  OFF = 1
  DRIVER_OVER = 2
  RUN = 3
  

class CAR(StrEnum):
  CX5 = "MAZDA CX-5"
  CX9 = "MAZDA CX-9"
  MAZDA3 = "MAZDA 3"
  MAZDA6 = "MAZDA 6"
  CX9_2021 = "MAZDA CX-9 2021"
  CX5_2022 = "MAZDA CX-5 2022"
  MAZDA3_2019 = "MAZDA 3 2019"
  CX_30 = "MAZDA CX-30"
  CX_50 = "MAZDA CX-50"
  CX_60 = "MAZDA CX-60"
  CX_70 = "MAZDA CX-70"
  CX_80 = "MAZDA CX-80"
  CX_90 = "MAZDA CX-90"


@dataclass
class MazdaCarInfo(CarInfo):
  package: str = "All"
  car_parts: CarParts = field(default_factory=CarParts.common([CarHarness.mazda]))


CAR_INFO: Dict[str, Union[MazdaCarInfo, List[MazdaCarInfo]]] = {
  CAR.CX5: MazdaCarInfo("Mazda CX-5 2017-21"),
  CAR.CX9: MazdaCarInfo("Mazda CX-9 2016-20"),
  CAR.MAZDA3: MazdaCarInfo("Mazda 3 2017-18"),
  CAR.MAZDA6: MazdaCarInfo("Mazda 6 2017-20"),
  CAR.CX9_2021: MazdaCarInfo("Mazda CX-9 2021-23", video_link="https://youtu.be/dA3duO4a0O4"),
  CAR.CX5_2022: MazdaCarInfo("Mazda CX-5 2022-24"),
  CAR.MAZDA3_2019: MazdaCarInfo("Mazda 3 2019-24"),
  CAR.CX_30: MazdaCarInfo("Mazda CX-30 2019-24"),
  CAR.CX_50: MazdaCarInfo("Mazda CX-50 2022-24"),
  CAR.CX_60: MazdaCarInfo("Mazda CX-60 unreleased"),
  CAR.CX_70: MazdaCarInfo("Mazda CX-70 unreleased"),
  CAR.CX_80: MazdaCarInfo("Mazda CX-80 unreleased"),
  CAR.CX_90: MazdaCarInfo("Mazda CX-90 2023"),
}


class LKAS_LIMITS:
  STEER_THRESHOLD = 6
  DISABLE_SPEED = 0    # kph
  ENABLE_SPEED = 0     # kph
  TI_STEER_THRESHOLD = 6
  TI_DISABLE_SPEED = 0    # kph
  TI_ENABLE_SPEED = 0     # kph



class Buttons:
  NONE = 0
  SET_PLUS = 1
  SET_MINUS = 2
  RESUME = 3
  CANCEL = 4
  TURN_ON = 5

FW_QUERY_CONFIG = FwQueryConfig(
  requests=[
    Request(
      [StdQueries.MANUFACTURER_SOFTWARE_VERSION_REQUEST],
      [StdQueries.MANUFACTURER_SOFTWARE_VERSION_RESPONSE],
      bus=0,
    ),
    Request(
      [StdQueries.TESTER_PRESENT_REQUEST, StdQueries.MANUFACTURER_SOFTWARE_VERSION_REQUEST],
      [StdQueries.TESTER_PRESENT_RESPONSE, StdQueries.MANUFACTURER_SOFTWARE_VERSION_RESPONSE],
      whitelist_ecus=[Ecu.engine],
    ),
    Request(
      [StdQueries.TESTER_PRESENT_REQUEST, StdQueries.MANUFACTURER_SOFTWARE_VERSION_REQUEST],
      [StdQueries.TESTER_PRESENT_RESPONSE, StdQueries.MANUFACTURER_SOFTWARE_VERSION_RESPONSE],
      bus=0,
      whitelist_ecus=[Ecu.eps, Ecu.abs, Ecu.fwdRadar, Ecu.fwdCamera, Ecu.shiftByWire],
    )
  ],
)


DBC = {
  CAR.CX5: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.CX9: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.MAZDA3: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.MAZDA6: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.CX9_2021: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.CX5_2022: dbc_dict('mazda_2017', 'mazda_radar'),
  CAR.MAZDA3_2019: dbc_dict('mazda_2019', None),
  CAR.CX_30: dbc_dict('mazda_2019', None),
  CAR.CX_50: dbc_dict('mazda_2019', None),
  CAR.CX_60: dbc_dict('mazda_2019', None),
  CAR.CX_70: dbc_dict('mazda_2019', None),
  CAR.CX_80: dbc_dict('mazda_2019', None),
  CAR.CX_90: dbc_dict('mazda_2019', None),
}

# Gen 1 hardware: same CAN messages and same camera
GEN1 = {CAR.CX5, CAR.CX9, CAR.CX9_2021, CAR.MAZDA3, CAR.MAZDA6, CAR.CX5_2022}
GEN2 = {CAR.MAZDA3_2019, CAR.CX_30, CAR.CX_50, CAR.CX_60, CAR.CX_70, CAR.CX_80, CAR.CX_90}
