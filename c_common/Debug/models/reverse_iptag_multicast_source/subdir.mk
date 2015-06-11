################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../models/reverse_iptag_multicast_source/reverse_iptag_multicast_source.c 

OBJS += \
./models/reverse_iptag_multicast_source/reverse_iptag_multicast_source.o 

C_DEPS += \
./models/reverse_iptag_multicast_source/reverse_iptag_multicast_source.d 


# Each subdirectory must supply rules for building sources it contributes
models/reverse_iptag_multicast_source/%.o: ../models/reverse_iptag_multicast_source/%.c
	@echo 'Building file: $<'
	@echo 'Invoking: Cross GCC Compiler'
	arm-none-eabi-gcc -I"C:\Users\zzalsar4\git\spinnaker_tools\include" -I"C:\MinGW\msys\1.0\share\arm-2013.11\lib\gcc\arm-none-eabi\4.8.1\include" -I"C:\MinGW\msys\1.0\share\arm-2013.11\arm-none-eabi\include" -O0 -g3 -Wall -c -fmessage-length=0 -MMD -MP -MF"$(@:%.o=%.d)" -MT"$(@:%.o=%.d)" -o "$@" "$<"
	@echo 'Finished building: $<'
	@echo ' '


