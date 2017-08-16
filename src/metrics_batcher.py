# -*- coding: utf-8 -*-

import collectd
import threading
import Queue
from timer import Timer


class MetricsBatcher(Timer):
    """
    Groups metrics in to batches based on max_batch_size and max_batch_interval
    """

    def __init__(self, max_batch_size, max_batch_interval, met_buffer):
        """
        Init MetricsBatcher with max_batch_size, max_batch_interval, and met_buffer
        """

        Timer.__init__(self, max_batch_interval, self._flush)

        # initiate max_batch_size and max_batch_interval
        self.max_batch_size = max_batch_size
        self.max_batch_interval = max_batch_interval

        # init batching queue to 2 * max_batch_size so that producer can still write while flushing
        self.queue = Queue.Queue(2 * max_batch_size)

        # init lock for flushing
        self.flushing_lock = threading.Lock()
        self.metrics_buffer = met_buffer

        # start timer
        self.start_timer()

        collectd.info('Initialized MetricsBatcher with max_batch_size %s, max_batch_interval %s' %
                      (max_batch_size, max_batch_interval))

    def push_item(self, item):
        """
        Add a new metric to the batching queue
        """

        self.queue.put(item)
        if self._batch_full():
            self._flush()

    def _flush(self):

        if self.queue.empty():
            collectd.debug('queue is empty')
            return
        if self.flushing_lock.acquire(False):
            batch = self._pop_batch()
            collectd.debug('flushing metrics with batch size %d' % len(batch))
            self.metrics_buffer.put_pending_batch(batch)
            self.reset_timer()
            self.flushing_lock.release()

    # Test whether we have enough metrics in batching queue to form a full batch
    def _batch_full(self):

        return self.queue.qsize() >= self.max_batch_size

    # Calculate the maximum batch we can group in to one batch
    def _batch_size(self):

        size = self.max_batch_size if self._batch_full() else self.queue.qsize()
        return size

    # Pops the maximum batch we can group from batching queue
    def _pop_batch(self):

        batch = []

        for i in range(self._batch_size()):
            batch.append(self.queue.get())

        return batch
