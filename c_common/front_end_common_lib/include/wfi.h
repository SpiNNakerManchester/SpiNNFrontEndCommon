/*
 * Copyright (c) 2020 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
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
    asm volatile("mcr p15, 0, r0, c7, c0, 4");
}
