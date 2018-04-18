static inline double get_wall_time();
static inline double get_cpu_time();

#ifdef _WIN32

// Windows

#include <Windows.h>

static inline double get_wall_time() {
    LARGE_INTEGER time, freq;
    if (!QueryPerformanceFrequency(&freq)) {
        //  Handle error
        return 0;
    }
    if (!QueryPerformanceCounter(&time)) {
        //  Handle error
        return 0;
    }
    return double(time.QuadPart) / freq.QuadPart;
}

static inline double get_cpu_time() {
    typedef unsigned long long ull;
    FILETIME a, b, kernelTime, userTime;
    if (GetProcessTimes(GetCurrentProcess(), &a, &b, &kernelTime, &userTime) == 0) {
        // Handle error
        return 0;
    }
    // Returns total user time.
    ULARGE_INTEGER uli;
    uli.LowPart = d.dwLowDateTime;
    uli.HighPart = d.dwHighDateTime;
    // Can be tweaked to include kernel times as well.
    return uli.QuadPart / 1e7;
}

#else // !_WIN32

// Posix/Linux

#include <time.h>
#include <sys/time.h>

static inline double get_wall_time() {
    struct timeval time;
    if (gettimeofday(&time, NULL)) {
        //  Handle error
        return 0;
    }
    return time.tv_sec + time.tv_usec / 1e6;
}

static inline double get_cpu_time() {
    return double(clock()) / CLOCKS_PER_SEC;
}

#endif
