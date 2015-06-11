################################################################################
# Automatically-generated file. Do not edit!
################################################################################

-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include models/reverse_iptag_multicast_source/subdir.mk
-include models/live_packet_gather/subdir.mk
-include models/command_sender_multicast_source/subdir.mk
-include front_end_common_lib/src/subdir.mk
-include front_end_common_lib/build/subdir.mk
-include subdir.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables 

# All Target
all: SpiNNFrontEndcommon_c_common

# Tool invocations
SpiNNFrontEndcommon_c_common: $(OBJS) $(USER_OBJS)
	@echo 'Building target: $@'
	@echo 'Invoking: Cross GCC Linker'
	arm-none-eabi-gcc  -o "SpiNNFrontEndcommon_c_common" $(OBJS) $(USER_OBJS) $(LIBS)
	@echo 'Finished building target: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(OBJS)$(C_DEPS)$(EXECUTABLES) SpiNNFrontEndcommon_c_common
	-@echo ' '

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets
