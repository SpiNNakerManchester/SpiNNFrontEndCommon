#ifndef _PARALLEL_QUEUE_
#define _PARALLEL_QUEUE_

#include <queue>
#include <thread>
#include <mutex>
#include <chrono>
#include <atomic>
#include <condition_variable>

using namespace std::literals::chrono_literals;

struct TimeoutQueueException : public std::exception {

  
};

template <typename T>
class PQueue {

 public:
  
  T pop() {

    std::unique_lock<std::mutex> mlock(mutex_);

    while (queue_.empty()){

      if((cond_.wait_for(mlock, 10*100ms)) == cv_status::timeout)
        throw TimeoutQueueException();
    }

    auto val = queue_.front();
    queue_.pop();

    return val;
  }

  void push(const T& item){

    std::unique_lock<std::mutex> mlock(mutex_);
    queue_.push(item);
    mlock.unlock();
    cond_.notify_one();
  }

  PQueue()=default;
  PQueue(const PQueue&) = delete;            // disable copying
  PQueue& operator=(const PQueue&) = delete; // disable assignment
  
 private:

  std::queue<T> queue_;
  std::mutex mutex_;
  std::condition_variable cond_;

};

#endif