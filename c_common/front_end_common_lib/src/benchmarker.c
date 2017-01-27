

static setup_timer(){
    // Configure timer 2 for timing things
    tc[T2_CONTROL] = 0;
    tc[T2_INT_CLR] = 1;
    tc[T2_LOAD] = START_CLOCK;
    tc[T2_BG_LOAD] = START_CLOCK;
    tc[T2_CONTROL] = 0xc2;
}

static start_timer(){
    tc[T2_LOAD] = START_CLOCK;
}

static uint32_t end_timer(){
    return START_CLOCK - count;
}
