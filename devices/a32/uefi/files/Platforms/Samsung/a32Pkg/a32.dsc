##
#  Copyright (c) 2011 - 2022, ARM Limited. All rights reserved.
#  Copyright (c) 2014, Linaro Limited. All rights reserved.
#  Copyright (c) 2015 - 2020, Intel Corporation. All rights reserved.
#  Copyright (c) 2018, Bingxing Wang. All rights reserved.
#  Copyright (c) Microsoft Corporation.
#
#  SPDX-License-Identifier: BSD-2-Clause-Patent
##

################################################################################
#
# Defines Section - statements that will be processed to create a Makefile.
#
################################################################################
[Defines]
  PLATFORM_NAME                  = a32
  PLATFORM_GUID                  = 9C945A0D-0D2E-43FA-8A86-E7B03FC23A02
  PLATFORM_VERSION               = 0.1
  DSC_SPECIFICATION              = 0x00010005
  OUTPUT_DIRECTORY               = Build/a32Pkg
  SUPPORTED_ARCHITECTURES        = AARCH64
  BUILD_TARGETS                  = RELEASE|DEBUG
  SKUID_IDENTIFIER               = DEFAULT
  FLASH_DEFINITION               = a32Pkg/a32.fdf
  USE_CUSTOM_DISPLAY_DRIVER      = 0

  #
  # 0 = MT6768
  # 1 = MT6769T
  # 2 = MT6769Z
  #
  SOC_TYPE                       = 1

!include MT6768Pkg/MT6768Pkg.dsc.inc

[PcdsFixedAtBuild]
  #
  # DDR Memory
  #
  gArmTokenSpaceGuid.PcdSystemMemoryBase|0x40000000

  #
  # UEFI Stack
  #
  gArmPlatformTokenSpaceGuid.PcdCPUCoresStackBase|0x40000000
  gArmPlatformTokenSpaceGuid.PcdCPUCorePrimaryStackSize|0x40000

  #
  # SMBIOS
  #
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemManufacturer|"Samsung"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemModel|"Galaxy A32 4G"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailModel|"a32"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailSku|"SM-A325F"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemBoardModel|"SM-A325F"

  #
  # Simple Frame Buffer
  #
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferWidth|1080
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferHeight|2400
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferColorDepth|32
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferXOffset|0

  #
  # Storage
  #
  gMediaTekPkgTokenSpaceGuid.PcdStorageIsEMMC|TRUE

[LibraryClasses]
  #
  # Memory Libraries
  #
  MemoryMapLib|a32Pkg/Library/MemoryMapDxeLib/MemoryMapDxeLib.inf

  #
  # Input Libraries
  #
  KeypadDeviceLib|a32Pkg/Library/KeypadDeviceLib/KeypadDeviceLib.inf

  #
  # UniXNU Libraries
  #
  UniXNULib|UniXNUPkg/Library/UniXNULib/UniXNULib.inf
  FdtLib|MdePkg/Library/BaseFdtLib/BaseFdtLib.inf

[LibraryClasses.common.SEC]
  MemoryMapLib|a32Pkg/Library/MemoryMapLib/MemoryMapLib.inf

[Components]
  # Read LK's FDT and publish its initrd, without the Redmi Note 9 RAM table.
  a32Pkg/Drivers/A32BootMemoryDxe/A32BootMemoryDxe.inf

  #
  # Input
  #
  SiliciumPkg/Drivers/KeypadDxe/KeypadDxe.inf
  SiliciumPkg/Drivers/KeypadDeviceDxe/KeypadDeviceDxe.inf

  #
  # UniXNU
  #
  UniXNUPkg/Application/UniXNU/UniXNU.inf
  UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf
  DarwinBootPkg/Driver/DarwinBoot.inf
