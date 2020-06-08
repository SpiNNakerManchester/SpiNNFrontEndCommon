/*
 * Copyright (c) 2017-2019 The University of Manchester
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

#ifndef __PLATFORM_H__
#define __PLATFORM_H__

static inline void * safe_malloc(uint bytes)
{
  void* p = sark_xalloc(sark.heap, bytes, 0, 0);
  if (p != NULL) {
      return p;
  }
  p = sark_xalloc(sv->sdram_heap, bytes, 0, ALLOC_LOCK);
  if (p == NULL)
  {
    io_printf(IO_BUF, "Failed to malloc %u bytes.\n", bytes);
    rt_error(RTE_MALLOC);
  }
  return p;
}

static inline void safe_xfree(void *ptr){
  uint ptr_int = (uint) ptr;
  if (ptr_int >= DTCM_BASE && ptr_int <= DTCM_TOP) {
      sark_xfree(sark.heap, ptr, 0);
  } else {
      sark_xfree(sv->sdram_heap, ptr, ALLOC_LOCK);
  }
}

#define MALLOC safe_malloc
#define FREE   safe_xfree

#endif  // __PLATFORN_H__
