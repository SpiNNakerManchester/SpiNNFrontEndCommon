/*
 * Copyright (c) 2020 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#pragma once
#include <stdint.h>

//! \file
//! \brief Wait for interrupt.

/*! \brief Wait for any interrupt to occur.
 *  \details Code resumes after the wait once the interrupt has been serviced.
 *      Inline version of code that appears in spin1_api so that we can
 *      get more compact code. For a description of what this actually does,
 *      see <a href="https://developer.arm.com/
documentation/ddi0311/d/system-control-coprocessor/cp15-register-descriptions/
cp15-c7-core-control-operations">the relevant ARM documentation</a>
 *      (it's hardware magic, specific to the ARM968).
 */
static inline void wait_for_interrupt(void) {
    register uint32_t value = 0;
    asm volatile("mcr p15, 0, %[value], c7, c0, 4" : : [value] "r" (value));
}
