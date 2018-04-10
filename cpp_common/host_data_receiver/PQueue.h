#ifndef _PARALLEL_QUEUE_
#define _PARALLEL_QUEUE_

#include <queue>
#include <thread>
#include <mutex>
#include <chrono>
#include <atomic>
#include <condition_variable>

using namespace std::literals::chrono_literals;

/// Exception throw when the queue times out
struct TimeoutQueueException: public std::exception {
};

/// A simple thread-aware queue that supports one writer and one reader
template<typename T>
class PQueue {
    /// How long to wait for the queue to have an element in it
    static constexpr auto const& TIMEOUT = 10 * 100ms;

public:
    /// Retrieve a value from the queue, or timeout with an exception
    T pop()
    {
	std::unique_lock<std::mutex> mlock(mutex);

	while (queue.empty()) {
	    if (cond.wait_for(mlock, TIMEOUT) == std::cv_status::timeout) {
		throw TimeoutQueueException();
	    }
        }

        auto val = std::move(queue.front());
        queue.pop();

        return val;
    }

    /// Add an item to the queue
    void push(const T& item) {
        std::unique_lock<std::mutex> mlock(mutex);
        queue.push(item);
        cond.notify_one();
    }

    PQueue() = default;
    PQueue(const PQueue&) = delete;            // disable copying
    PQueue& operator=(const PQueue&) = delete; // disable assignment

private:
    /// The implemetation of the queue
    std::queue<T> queue;
    /// The lock on the queue
    std::mutex mutex;
    /// The condition variable used to signal that an item was added
    std::condition_variable cond;
};

#endif
