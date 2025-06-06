#
# Copyright 2025 Variscite Ltd.
# Copyright (c) 2024 NXP
#
# SPDX-License-Identifier: Apache-2.0
#

if(CONFIG_SOC_MIMX8ML8_M7)
  board_set_debugger_ifnset(jlink)
  board_set_flasher_ifnset(jlink)

  board_runner_args(jlink "--device=MIMX8ML8_M7")
  include(${ZEPHYR_BASE}/boards/common/jlink.board.cmake)
endif()
