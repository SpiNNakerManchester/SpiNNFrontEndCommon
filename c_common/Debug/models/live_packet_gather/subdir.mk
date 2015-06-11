################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../models/live_packet_gather/live_packet_gather.c 

OBJS += \
./models/live_packet_gather/live_packet_gather.o 

C_DEPS += \
./models/live_packet_gather/live_packet_gather.d 


# Each subdirectory must supply rules for building sources it contributes
models/live_packet_gather/%.o: ../models/live_packet_gather/%.c
	@echo 'Building file: $<'
	@echo 'Invoking: Cross GCC Compiler'
	arm-none-eabi-gcc -I"C:\Users\zzalsar4\git\spinnaker_tools\include" -I"C:\MinGW\msys\1.0\share\arm-2013.11\lib\gcc\arm-none-eabi\4.8.1\include" -I"C:\MinGW\msys\1.0\share\arm-2013.11\arm-none-eabi\include" -O0 -g3 -Wall -c -fmessage-length=0 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@:%.o=%.d)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


